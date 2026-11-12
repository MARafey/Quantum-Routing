"""Honest benchmark: standard vs warm-started Dürr–Høyer on identical cost tables.

Run:  uv run qroute-bench   (writes backend/results/quantum_warmstart_benchmark.json)
coverage_pct: standard = 100*queries_to_min/N; warm = 100*(queries_to_min + heuristic_evals)/N.
Medians/means of queries_to_min and coverage are over successful runs only (success = optimum found
within the budget); the success rate is reported separately."""

from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import numpy as np

from . import pool, vrp

OUT = Path(__file__).resolve().parents[2] / "results" / "quantum_warmstart_benchmark.json"
QSEEDS = range(5)


def bench_scenario(region: str, seed: int) -> list[dict]:
    sc = pool.random_scenario(seed, region)
    hubs, sites = sc["hubs"], sc["sites"]
    k, n = len(hubs), len(sites)
    allp = hubs + sites
    idx = pool.pool_lookup([(p["name"], p["lat"], p["lon"]) for p in allp], region)
    M, _ = pool.pool_matrix(region)
    D = np.ascontiguousarray(M[np.ix_(idx, idx)])
    N = vrp.num_plans(n, k)
    costs = vrp.evaluate_all(D, k, n, False)
    order = np.argsort(costs, kind="stable")
    gmin = float(costs.min())
    h = vrp.classical_heuristic_plan(D, k, n, False)
    h_opt = bool(abs(h["cost"] - gmin) <= 1e-9 * max(1.0, gmin))
    rows = []
    for qs in QSEEDS:
        std = vrp.quantum_min_search(costs, qs, presorted=order)
        ws = vrp.quantum_min_search(costs, qs, init_index=h["index"], presorted=order)
        for variant, r, extra in (("standard", std, 0), ("warm", ws, h["evals"])):
            qtm = r["queries_to_min"]
            rows.append({
                "region": region, "scenario_seed": seed, "quantum_seed": qs, "variant": variant,
                "k": k, "n": n, "N": N, "queries_to_min": qtm, "success": qtm is not None,
                "coverage_pct": 100 * (qtm + extra) / N if qtm is not None else None,
                "budget": r["budget"], "heuristic_evals": extra,
                "heuristic_optimal": h_opt if variant == "warm" else None,
                "heuristic_gap_pct": 100 * (h["cost"] - gmin) / gmin if variant == "warm" else None,
            })
    return rows


def _stats(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["success"]]
    q = [r["queries_to_min"] for r in ok]
    c = [r["coverage_pct"] for r in ok]
    return {"runs": len(rows), "success_rate": len(ok) / len(rows) if rows else None,
            "median_queries_to_min": st.median(q) if q else None,
            "mean_queries_to_min": st.fmean(q) if q else None,
            "median_coverage_pct": st.median(c) if c else None}


def summarise(rows: list[dict]) -> dict:
    out = {}
    for region in dict.fromkeys(r["region"] for r in rows):
        rr = [r for r in rows if r["region"] == region]
        entry = {v: _stats([r for r in rr if r["variant"] == v]) for v in ("standard", "warm")}
        by = {}
        for r in rr:
            by.setdefault((r["scenario_seed"], r["quantum_seed"]), {})[r["variant"]] = r
        pairs = [p for p in by.values() if p["standard"]["success"] and p["warm"]["success"]]
        cov = [p["standard"]["coverage_pct"] / p["warm"]["coverage_pct"] for p in pairs]
        qr = [p["standard"]["queries_to_min"] / p["warm"]["queries_to_min"]
              for p in pairs if p["warm"]["queries_to_min"] > 0]
        entry["median_ratio_coverage_std_over_warm"] = st.median(cov) if cov else None
        entry["median_ratio_queries_std_over_warm"] = st.median(qr) if qr else None
        entry["pairs_excluded_from_queries_ratio_warm_zero"] = sum(
            p["warm"]["queries_to_min"] == 0 for p in pairs)
        entry["heuristic_found_optimum_pct"] = 100 * st.fmean(
            r["heuristic_optimal"] for r in rr if r["variant"] == "warm")
        entry["median_heuristic_gap_pct"] = st.median(r["heuristic_gap_pct"] for r in rr if r["variant"] == "warm")
        out[region] = entry
    return out


def _f(x, spec=".1f"):
    return "-" if x is None else format(x, spec)


def print_table(summary: dict) -> None:
    hdr = (f"{'region':<15}{'variant':<9}{'runs':>5}{'succ%':>7}{'med q2min':>11}{'mean q2min':>12}"
           f"{'med cov%':>10}{'cov ratio':>10}{'q ratio':>9}{'heur opt%':>10}")
    print(hdr)
    for region, e in summary.items():
        for v in ("standard", "warm"):
            s = e[v]
            last = (_f(e["median_ratio_coverage_std_over_warm"], ".2f"), _f(e["median_ratio_queries_std_over_warm"], ".2f"),
                    _f(e["heuristic_found_optimum_pct"], ".0f")) if v == "warm" else ("", "", "")
            print(f"{region:<15}{v:<9}{s['runs']:>5}{100 * s['success_rate']:>7.1f}"
                  f"{_f(s['median_queries_to_min'], '.0f'):>11}{_f(s['mean_queries_to_min'], '.0f'):>12}"
                  f"{_f(s['median_coverage_pct'], '.4f'):>10}{last[0]:>10}{last[1]:>9}{last[2]:>10}")


def main() -> None:
    t0 = time.time()
    plan = [("pakistan", range(100, 120))] + [(r, range(100, 105)) for r in pool.REGIONS if r != "pakistan"]
    rows: list[dict] = []
    for region, seeds in plan:
        for seed in seeds:
            rows += bench_scenario(region, seed)
            print(f"[bench] {region} seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    summary = summarise(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "rows": rows, "quantum_seeds": list(QSEEDS),
                               "note": __doc__}, indent=1), encoding="utf-8")
    print_table(summary)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
