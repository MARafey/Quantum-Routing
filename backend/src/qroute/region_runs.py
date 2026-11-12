"""Runs one fixed-seed random scenario per region through run_plan and saves the comparison table.

Usage: uv run qroute-regions     (writes backend/results/region_runs.json)
Uses the same code path as POST /api/run, so the numbers match what the web app shows.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import pool, run, vrp
from .dp_baseline import subset_dp_makespan

OUT = Path(__file__).resolve().parents[2] / "results" / "region_runs.json"
SEEDS = {"pakistan": 7, "turkiye-syria": 3, "bengal-floods": 5, "nepal-himalaya": 5}


def main() -> None:
    ex = vrp.make_pool()
    rows = []
    try:
        for region, seed in SEEDS.items():
            sc = pool.random_scenario(seed, region)
            t0 = time.perf_counter()
            res = run.run_plan(sc["hubs"], sc["sites"], ex, False, region)
            wall = time.perf_counter() - t0
            m = res["methods"]
            allp = sc["hubs"] + sc["sites"]
            idx = pool.pool_lookup([(q["name"], q["lat"], q["lon"]) for q in allp], region)
            M, _ = pool.pool_matrix(region)
            D = np.ascontiguousarray(M[np.ix_(idx, idx)])
            dp = subset_dp_makespan(D, res["k"], res["n"], False)
            row = {"region": region, "seed": seed, "k": res["k"], "n": res["n"], "N": res["N"], "qubits": res["qubits"],
                   "matrix_source": res["matrix_source"], "request_s": round(wall, 2),
                   "best_makespan_h": round(res["best"]["makespan_s"] / 3600, 2), "methods": {}}
            for key, d in m.items():
                row["methods"][key] = {k: d.get(k) for k in ("ms", "evaluated", "queries", "queries_to_min", "heuristic_evals",
                                                              "coverage_pct", "optimal", "makespan_s", "workers")}
            row["subset_dp"] = {"ms": round(dp["ms"], 1), "states": dp["states"], "makespan_s": dp["makespan_s"],
                                "matches_brute_force": abs(dp["makespan_s"] - res["best"]["makespan_s"]) < 1.0}
            rows.append(row)
            print(f"   subset DP: {dp['ms']:.0f} ms, makespan matches: {row['subset_dp']['matches_brute_force']}")
            print(f"{region:15s} k={res['k']} n={res['n']} N={res['N']:,} " + "  ".join(
                f"{k}: {d['ms'] / 1000:.2f}s {d['coverage_pct']:.3f}% opt={d['optimal']}" for k, d in m.items()), flush=True)
    finally:
        ex.shutdown()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows}, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
