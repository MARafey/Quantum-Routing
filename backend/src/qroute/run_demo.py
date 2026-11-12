"""Run every experiment and export results.json for the React frontend.

Usage:  uv run qroute-demo            (full run, a few minutes)
        uv run qroute-demo --quick    (fewer restarts / reps, for a smoke test)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from . import model as M
from .baselines import assignment_energy, brute_force, greedy, simulated_annealing
from .cluster import solve_clustered
from .grover_min import experiment as grover_experiment
from .network import FLOOD_ZONE, LINES, SHELTERS, Network, build_network
from .qaoa import analyse, run_qaoa
from .raptor import Raptor

ROOT = Path(__file__).resolve().parents[3]
OUT_FILES = [ROOT / "backend" / "results" / "results.json", ROOT / "frontend" / "public" / "results.json"]

SMALL_GROUPS = [("Clifton", 80), ("DHA", 70), ("Korangi", 90), ("Tower", 60)]
LARGE_GROUPS = [(o, s, d) for d, sizes in ((0, [80, 70, 90, 60, 75, 65]), (10, [55, 85, 60, 70, 50, 80]))
                for o, s in zip(["Clifton", "DHA", "Korangi", "Tower", "Keamari", "Lyari"], sizes)]


def journey_json(net: Network, j, cost: float) -> dict:
    legs = []
    for l in j.legs:
        if l.kind == "bus":
            r = net.routes[l.route]
            path = [[net.stops[s].lat, net.stops[s].lon] for s in r.stops[l.board_idx:l.alight_idx + 1]]
            legs.append({"kind": "bus", "line": r.name, "dep": l.dep, "arr": l.arr, "from": net.stops[l.from_stop].name,
                         "to": net.stops[l.to_stop].name, "path": path})
        else:
            legs.append({"kind": "walk", "dep": l.dep, "arr": l.arr, "from": net.stops[l.from_stop].name,
                         "to": net.stops[l.to_stop].name,
                         "path": [[net.stops[l.from_stop].lat, net.stops[l.from_stop].lon],
                                  [net.stops[l.to_stop].lat, net.stops[l.to_stop].lon]]})
    return {"shelter": net.stops[j.target].name, "travel_min": j.arr - j.dep, "transfers": j.transfers,
            "arrival": j.arr, "cost_per_person": cost, "legs": legs}


def evaluate(net: Network, inst: M.Instance, assign: list[int]) -> dict:
    """Interpretable metrics for an assignment."""
    seg_load: dict[tuple, int] = {}
    shelter_load: dict[str, int] = {}
    person_min = 0.0
    for g, r in enumerate(assign):
        j = inst.options[g][r]
        n = inst.groups[g].size
        person_min += n * (j.arr - j.dep)
        for s in j.segments():
            seg_load[s] = seg_load.get(s, 0) + n
        name = net.stops[j.target].name
        shelter_load[name] = shelter_load.get(name, 0) + n
    factors = [load / net.routes[s[0]].capacity[s[1]] for s, load in seg_load.items()]
    return {
        "person_minutes": person_min,
        "avg_travel_min": person_min / sum(g.size for g in inst.groups),
        "max_bus_load_factor": max(factors) if factors else 0,
        "overloaded_bus_segments": sum(f > 1.0 for f in factors),
        "shelter_load": shelter_load,
        "shelter_overflow": sum(max(0, v - M.SHELTER_CAP[k]) for k, v in shelter_load.items()),
    }


def method_row(net, inst, res, exact_e) -> dict:
    a = res["assignment"]
    return {"method": res["method"], "assignment": a, "energy": res["energy"],
            "gap_pct": 100 * (res["energy"] - exact_e) / exact_e, "seconds": res.get("seconds"),
            "metrics": evaluate(net, inst, a)}


def instance_json(net, inst) -> dict:
    return {
        "groups": [{"id": g.id, "origin": g.origin, "size": g.size, "dep": g.dep,
                    "lat": net.stops[net.stop_by_name(g.origin)].lat, "lon": net.stops[net.stop_by_name(g.origin)].lon}
                   for g in inst.groups],
        "K": inst.K, "num_vars": inst.n,
        "options": [[journey_json(net, j, M.journey_cost(j)) for j in opts] for opts in inst.options],
        "penalty_A": inst.penalty,
    }


def independent(inst: M.Instance) -> dict:
    a = [0] * len(inst.groups)  # options are sorted, 0 = each group's own fastest RAPTOR journey
    return {"method": "Independent RAPTOR (no coordination)", "assignment": a, "energy": assignment_energy(inst, a)}


def network_json(net: Network) -> dict:
    lines = []
    seen = set()
    for r in net.routes:
        base = r.name.rsplit(" ", 1)[0]
        if r.name.endswith("→"):
            lines.append({"name": base, "path": [[net.stops[s].lat, net.stops[s].lon] for s in r.stops],
                          "trips": len(r.trips)})
            seen.add(base)
    return {
        "stops": [{"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon, "landmark": s.landmark} for s in net.stops],
        "lines": lines, "damaged": [[list(p) for p in poly] for poly in net.damaged],
        "flood_zone": FLOOD_ZONE,
        "shelters": [{"name": s, "capacity": M.SHELTER_CAP[s]} for s in SHELTERS],
        "num_routes": len(net.routes), "num_trips": net.num_trips(), "num_lines": len(LINES),
    }


def grover_labels(net: Network) -> dict[int, np.ndarray]:
    """Collect real RAPTOR arrival labels (origin x shelter x round x departure) as minimum-search inputs."""
    raptor = Raptor(net)
    labels = []
    for o in FLOOD_ZONE:
        for dep in (0, 8, 16):
            res = raptor.run(net.stop_by_name(o), dep, 4)
            for s in SHELTERS:
                t = net.stop_by_name(s)
                for k in range(1, len(res.arr)):
                    if res.arr[k][t] < 10**8:
                        labels.append(res.arr[k][t] - dep + 0.01 * len(labels))  # tiny tiebreak -> unique min
    labels = np.array(labels)
    rng = np.random.default_rng(1)
    return {N: rng.choice(labels, N, replace=False) for N in (8, 16, 32, 64) if N <= len(labels)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    restarts = 2 if args.quick else 4
    reps_list = [1, 2] if args.quick else [1, 2, 3]
    t_start = time.perf_counter()
    net = build_network()
    out: dict = {"network": network_json(net), "generated": time.strftime("%Y-%m-%d %H:%M:%S")}

    # ---------- Small instance: full quantum vs exact comparison ----------
    print("[1/4] Small instance (4 groups x 3 options = 12 qubits)")
    groups = [M.Group(i, o, s, 0) for i, (o, s) in enumerate(SMALL_GROUPS)]
    inst = M.build_instance(net, groups, 3)
    bf = brute_force(inst)
    exact_e, worst_e = bf["energy"], bf["worst_energy"]
    methods = [method_row(net, inst, r, exact_e) for r in (independent(inst), greedy(inst), simulated_annealing(inst), bf)]
    qaoa_runs = []
    for variant in ("penalty", "xy"):
        for reps in reps_list:
            res = run_qaoa(inst, reps=reps, variant=variant, restarts=restarts)
            a = analyse(inst, res, exact_e, worst_e)
            qaoa_runs.append(a)
            print(f"   {variant:7s} p={reps}: P(feasible)={a['p_feasible']:.3f} P(opt)={a['p_optimal']:.3f} "
                  f"approx={a['approx_ratio'] if a['approx_ratio'] is None else round(a['approx_ratio'], 3)} "
                  f"depth={a['circuit_depth']} cx={a['cx_count']} {a['seconds']:.1f}s")
            if a["best_sampled_assignment"] is not None:
                label = f"QAOA {'XY-mixer' if variant == 'xy' else 'penalty'} p={reps}"
                methods.append(method_row(net, inst, {"method": label, "assignment": a["best_sampled_assignment"],
                                                      "energy": a["best_sampled_energy"], "seconds": a["seconds"]},
                                          exact_e))
    out["small"] = {**instance_json(net, inst), "exact_energy": exact_e, "worst_energy": worst_e,
                    "landscape": bf["all_energies"].tolist(), "methods": methods, "qaoa": qaoa_runs}
    for m in methods:
        print(f"   {m['method']:40s} E={m['energy']:10.1f} gap={m['gap_pct']:6.2f}%  {m['assignment']}")

    # ---------- Large instance: clustered QAOA ----------
    print("[2/4] Large instance (12 groups x 3 options = 36 variables, clustered QAOA)")
    lgroups = [M.Group(i, o, s, d) for i, (o, s, d) in enumerate(LARGE_GROUPS)]
    linst = M.build_instance(net, lgroups, 3)
    lbf = brute_force(linst)
    gr = greedy(linst)
    cl = solve_clustered(linst, init_assign=[0] * len(lgroups), cluster_size=4, sweeps=2, reps=2)
    lmethods = [method_row(net, linst, r, lbf["energy"])
                for r in (independent(linst), gr, simulated_annealing(linst, steps=8000), lbf, cl)]
    out["large"] = {**instance_json(net, linst), "exact_energy": lbf["energy"], "methods": lmethods,
                    "clusters": cl["clusters"], "trace": cl["trace"], "sub_stats": cl["sub_stats"]}
    for m in lmethods:
        print(f"   {m['method']:40s} E={m['energy']:10.1f} gap={m['gap_pct']:6.2f}%")

    # ---------- Grover / Dürr–Høyer query counts ----------
    print("[3/4] Dürr–Høyer minimum search over RAPTOR labels")
    rows = grover_experiment(grover_labels(net), trials=20 if args.quick else 40)
    out["grover"] = rows
    for r in rows:
        print(f"   N={r['N']:3d} qubits={r['qubits']} classical={r['classical_comparisons']:3d} "
              f"quantum mean queries to min={r['mean_queries_to_min']} success={r['success_rate']:.2f}")

    print("[4/4] Writing results")
    out["runtime_seconds"] = time.perf_counter() - t_start
    for f in OUT_FILES:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, default=_np, indent=1))
        print("   wrote", f)


def _np(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


if __name__ == "__main__":
    main()
