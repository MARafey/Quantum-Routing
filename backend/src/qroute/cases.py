"""Three real disaster-relief cases + the `qroute-cases` CLI that precomputes their JSON results."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from . import geo, vrp

ROOT = Path(__file__).resolve().parents[3]
OUT_DIRS = [ROOT / "backend" / "results" / "cases", ROOT / "frontend" / "public" / "cases"]
SEED = 7

CASES = [
    {"id": "sindh-floods-2022", "title": "Sindh floods 2022: one relief convoy", "region": "Pakistan",
     "disaster": "2022 Pakistan floods (Sindh)", "return_to_depot": False,
     "story": ("A single convoy leaves Karachi with tents, food and water for ten flooded districts up the Indus. "
               "Roads cut by the flood make every extra detour cost hours, and the order of stops decides "
               "when the last town finally receives aid. With 10 stops there are 3.6 million possible orders."),
     "depots": [("Karachi", 24.8607, 67.0011)],
     "sites": [("Hyderabad", 25.3960, 68.3578), ("Thatta", 24.7461, 67.9236), ("Badin", 24.6560, 68.8370),
               ("Mirpur Khas", 25.5276, 69.0111), ("Nawabshah", 26.2442, 68.4100), ("Dadu", 26.7319, 67.7750),
               ("Larkana", 27.5600, 68.2264), ("Sukkur", 27.7052, 68.8574), ("Jacobabad", 28.2769, 68.4514),
               ("Khairpur", 27.5295, 68.7592)]},
    {"id": "pakistan-floods-3-hubs", "title": "Pakistan floods: three convoys from three hubs",
     "region": "Pakistan", "disaster": "2022 Pakistan floods (national response)", "return_to_depot": False,
     "story": ("Relief stocks sit in Karachi, Lahore and Peshawar, and eight stricken districts lie in between. "
               "Choosing which hub serves which town matters as much as the visiting order, because the aid "
               "effort is only as fast as its slowest convoy. Splitting 8 sites across 3 hubs gives 1.8 million plans."),
     "depots": [("Karachi", 24.8607, 67.0011), ("Lahore", 31.5204, 74.3587), ("Peshawar", 34.0151, 71.5249)],
     "sites": [("Swat / Mingora", 34.7717, 72.3600), ("Dera Ismail Khan", 31.8314, 70.9019),
               ("Rajanpur", 29.1044, 70.3301), ("Dera Ghazi Khan", 30.0489, 70.6455),
               ("Jacobabad", 28.2769, 68.4514), ("Sukkur", 27.7052, 68.8574),
               ("Muzaffargarh", 30.0736, 71.1805), ("Dera Murad Jamali", 28.5466, 68.2231)]},
    {"id": "turkiye-syria-quake-2023", "title": "Türkiye–Syria earthquake 2023: cross-border relief",
     "region": "Türkiye / Syria", "disaster": "February 2023 Kahramanmaraş earthquakes", "return_to_depot": False,
     "story": ("Two logistics hubs, Adana and Gaziantep, must reach nine quake-hit cities on both sides of the "
               "border, where the first 72 hours decide survival. Which hub covers Antakya or Aleppo, and in "
               "what order, changes when the last city is reached by hours. That is 3.6 million plans."),
     "depots": [("Adana", 37.0000, 35.3213), ("Gaziantep", 37.0662, 37.3833)],
     "sites": [("Kahramanmaraş", 37.5858, 36.9371), ("Antakya", 36.2021, 36.1600), ("Malatya", 38.3552, 38.3095),
               ("Adıyaman", 37.7648, 38.2786), ("Osmaniye", 37.0742, 36.2478), ("İskenderun", 36.5872, 36.1735),
               ("Aleppo", 36.2021, 37.1343), ("Idlib", 35.9306, 36.6339), ("Şanlıurfa", 37.1591, 38.7969)]},
]


def _solution(D, idx, k, n, ret):
    return vrp.decode(idx, D, k, n, ret)


def run_case(case: dict, pool, legs_mode: str = "all", warm: bool = False, log=print) -> dict:
    depots, sites = case["depots"], case["sites"]
    k, n, ret = len(depots), len(sites), bool(case.get("return_to_depot", False))
    pts = [(d[1], d[2]) for d in depots] + [(s[1], s[2]) for s in sites]
    names = [d[0] for d in depots] + [s[0] for s in sites]
    N = vrp.num_plans(n, k)
    D, source = geo.travel_matrix(pts)
    log(f"[{case['id']}] N={N:,} matrix={source}")

    costs = vrp.evaluate_all(D, k, n, ret)
    gmin = float(costs.min())

    b = vrp.brute_force(D, k, n, ret)
    if warm:
        vrp.parallel_brute_force(D, k, n, ret, pool)
    p = vrp.parallel_brute_force(D, k, n, ret, pool)
    qr = vrp.quantum_min_search(costs, SEED)

    def opt(c):
        return bool(abs(c - gmin) <= 1e-9 * max(1.0, abs(gmin)))

    bs, ps, qs = (_solution(D, r["index"], k, n, ret) for r in (b, p, qr))
    samples = [{"q": s["q"], "solution": _solution(D, s["index"], k, n, ret), "cost_s": s["cost_s"],
                "improved": s["improved"]} for s in qr["samples"] if s["cost_s"] is not None]
    qtm = qr["queries_to_min"]
    methods = {
        "brute": {"ms": b["ms"], "evaluated": b["evaluated"], "solution": bs, "cost_s": b["cost"],
                  "optimal": opt(b["cost"])},
        "parallel": {"ms": p["ms"], "evaluated": p["evaluated"], "workers": p["workers"], "solution": ps,
                     "cost_s": p["cost"], "optimal": opt(p["cost"])},
        "quantum": {"ms": qr["ms"], "queries": qr["queries"], "queries_to_min": qtm, "budget": qr["budget"],
                    "qubits": qr["qubits"], "backend": qr["backend"], "samples": samples, "solution": qs,
                    "cost_s": qr["cost"], "optimal": opt(qr["cost"]),
                    "break_even_us": b["ms"] * 1000 / qtm if qtm else None,
                    "break_even_us_parallel": p["ms"] * 1000 / qtm if qtm else None},
    }

    # road geometry
    pairs = [(i, j) for i in range(len(pts)) for j in range(len(pts)) if i != j]
    want = set(pairs)
    if legs_mode != "all":
        want = set()
        sols = [bs, ps, qs] + [s["solution"] for s in samples[:60]]
        for s in sols:
            for r in s["routes"]:
                want |= {(r[t], r[t + 1]) for t in range(len(r) - 1)}
    legs = {}
    for t, (i, j) in enumerate(pairs):
        if (i, j) in want and source == "osrm":
            if t % 20 == 0:
                log(f"  legs {t}/{len(pairs)}")
            legs[f"{i}-{j}"] = geo.route_geometry(pts[i], pts[j])
        else:
            legs[f"{i}-{j}"] = [[round(pts[i][0], 5), round(pts[i][1], 5)], [round(pts[j][0], 5), round(pts[j][1], 5)]]

    return {
        "id": case["id"], "title": case["title"], "region": case["region"], "disaster": case["disaster"],
        "story": case["story"], "objective": "makespan", "return_to_depot": ret, "k": k, "n": n, "N": N,
        "qubits": qr["qubits"], "matrix_source": source,
        "points": [{"name": nm, "lat": la, "lon": lo, "kind": "depot" if i < k else "site"}
                   for i, (nm, (la, lo)) in enumerate(zip(names, pts))],
        "duration_matrix": D.round(1).tolist(), "legs": legs, "methods": methods,
        "scaling": vrp.scaling(k, [{"N": N, "queries_to_min": qtm, "evals_per_s": N / (b["ms"] / 1000)}]),
    }


def main() -> None:
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    pool = vrp.make_pool()
    index, measured, rows = [], {}, []
    try:
        for case in CASES:
            r = run_case(case, pool, "all", warm=True)
            for d in OUT_DIRS:
                (d / f"{r['id']}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            m = r["methods"]
            index.append({"id": r["id"], "title": r["title"], "region": r["region"], "disaster": r["disaster"],
                          "k": r["k"], "n": r["n"], "N": r["N"], "qubits": r["qubits"]})
            measured.setdefault(r["k"], []).append(
                {"N": r["N"], "queries_to_min": m["quantum"]["queries_to_min"],
                 "evals_per_s": r["N"] / (m["brute"]["ms"] / 1000)})
            rows.append((r["id"], r["N"], m["brute"]["ms"], m["parallel"]["ms"], m["quantum"]["ms"],
                         m["quantum"]["queries_to_min"], m["quantum"]["break_even_us"],
                         m["quantum"]["optimal"], r["matrix_source"]))
    finally:
        pool.shutdown()
    all_measured = [x for v in measured.values() for x in v]
    scaling = {str(k): vrp.scaling(k, all_measured) for k in (1, 2, 3)}
    for d in OUT_DIRS:
        (d / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        (d / "scaling.json").write_text(json.dumps(scaling), encoding="utf-8")
    print(f"{'case':26s} {'N':>10s} {'brute ms':>9s} {'par ms':>8s} {'quant ms':>9s} {'q->min':>7s} "
          f"{'breakeven us':>12s} {'opt':>4s} source")
    for cid, N, bm, pm, qm, qtm, be, ok, src in rows:
        print(f"{cid:26s} {N:10,d} {bm:9.0f} {pm:8.0f} {qm:9.0f} {qtm!s:>7s} "
              f"{(be if be is not None else float('nan')):12.2f} {ok!s:>4s} {src}")


if __name__ == "__main__":
    sys.exit(main())
