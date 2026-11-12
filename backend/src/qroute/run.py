"""Fast single-screen run path: matrix slice, three solvers, road geometry for the optimum only."""

from __future__ import annotations

import time

import numpy as np

from . import geo, pool, vrp

SEED = 7


def _downsample(pts: list[list[float]], m: int = 1500) -> list[list[float]]:
    if len(pts) <= m:
        return pts
    idx = np.linspace(0, len(pts) - 1, m).round().astype(int)
    return [pts[i] for i in idx]


def _convoy_geometry(coords: list[tuple[float, float]]) -> tuple[list[list[float]], float]:
    straight = [[round(a, 5), round(b, 5)] for a, b in coords]
    if len(coords) < 2:
        return straight, 0.0
    hav = sum(geo.haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1)) / 1000
    cs = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in coords)
    try:
        d = geo._get_json(f"{geo.OSRM}/route/v1/driving/{cs}?overview=full&geometries=geojson")
        r = d["routes"][0]
        line = [[round(lat, 5), round(lon, 5)] for lon, lat in r["geometry"]["coordinates"]]
        return _downsample(line), round(r["distance"] / 1000, 1)
    except Exception:
        return straight, round(hav, 1)


def run_plan(hubs: list[dict], sites: list[dict], pool_executor, return_to_depot: bool = False) -> dict:
    k, n = len(hubs), len(sites)
    allp = list(hubs) + list(sites)
    N = vrp.num_plans(n, k)
    idx = pool.pool_lookup([(p["name"], p["lat"], p["lon"]) for p in allp])
    if idx is not None:
        M, src = pool.pool_matrix()
        D = np.ascontiguousarray(M[np.ix_(idx, idx)])
        source = src + "-pool"
    else:
        D, source = geo.travel_matrix([(p["lat"], p["lon"]) for p in allp])
    ret = bool(return_to_depot)

    t0 = time.perf_counter()
    costs = vrp.evaluate_all(D, k, n, ret)  # oracle table, not counted in quantum ms
    oracle_ms = 1000 * (time.perf_counter() - t0)
    gmin = float(costs.min())
    b = vrp.brute_force(D, k, n, ret)
    p = vrp.parallel_brute_force(D, k, n, ret, pool_executor)
    qr = vrp.quantum_min_search(costs, SEED)

    def opt(c):
        return bool(abs(c - gmin) <= 1e-9 * max(1.0, abs(gmin)))

    bs, ps, qs = (vrp.decode(r["index"], D, k, n, ret) for r in (b, p, qr))
    qtm = qr["queries_to_min"]
    samples = [{"q": s["q"], "routes": vrp.decode(s["index"], D, k, n, ret)["routes"]}
               for s in qr["samples"] if s["cost_s"] is not None]
    if len(samples) > 150:
        keep = np.linspace(0, len(samples) - 1, 150).round().astype(int)
        samples = [samples[i] for i in sorted(set(keep.tolist()))]

    pts = [(q["lat"], q["lon"]) for q in allp]
    geom, dist = [], []
    for r in bs["routes"]:
        g, km = _convoy_geometry([pts[i] for i in r] + ([pts[r[0]]] if ret and len(r) > 1 else []))
        geom.append(g)
        dist.append(km)

    return {
        "k": k, "n": n, "N": N, "qubits": qr["qubits"], "matrix_source": source,
        "points": [{"name": q["name"], "lat": q["lat"], "lon": q["lon"], "kind": "hub" if i < k else "site"}
                   for i, q in enumerate(allp)],
        "methods": {
            "brute": {"ms": b["ms"], "evaluated": b["evaluated"], "coverage_pct": 100.0,
                      "optimal": opt(b["cost"]), "makespan_s": bs["makespan_s"]},
            "parallel": {"ms": p["ms"], "evaluated": p["evaluated"], "workers": p["workers"],
                         "coverage_pct": 100.0, "optimal": opt(p["cost"]), "makespan_s": ps["makespan_s"]},
            "quantum": {"ms": qr["ms"], "oracle_table_ms": oracle_ms, "queries": qr["queries"],
                        "queries_to_min": qtm,
                        "coverage_pct": 100 * qtm / N if qtm is not None else None,
                        "total_coverage_pct": 100 * qr["queries"] / N, "backend": qr["backend"],
                        "optimal": opt(qr["cost"]), "makespan_s": qs["makespan_s"], "samples": samples},
        },
        "best": {"routes": bs["routes"], "makespan_s": bs["makespan_s"], "total_s": bs["total_s"],
                 "geometry": geom, "distance_km": dist},
    }
