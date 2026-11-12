"""TSPLIB benchmark: Durr-Hoyer minimum finding over the index register vs brute force / Held-Karp."""
from __future__ import annotations

import inspect
import json
import math
import time
from pathlib import Path

import numpy as np

from .vrp import quantum_min_search

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tsplib"

REFERENCES = [
    {"id": "arXiv 2212.02735", "claim": "Grover adaptive search for TSP: 7-node TSP needs 31 qubits; optimal-solution success rate 86.71%"},
    {"id": "ICTC 2025 F01-4", "claim": "Standard Grover TSP: 24 qubits for 4 cities, 56 qubits for 5 cities"},
    {"id": "arXiv 2106.05948", "claim": "D-Wave hybrid on TSPLIB burma14: best hybrid result ~6.7% above optimum"},
    {"id": "arXiv 2012.04984", "claim": "D-Wave studies on TSPLIB instances (burma14 / ulysses16 class)"},
]


def read_tsp(path) -> np.ndarray:
    pts, on = [], False
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s == "NODE_COORD_SECTION":
            on = True
        elif s == "EOF":
            on = False
        elif on and s:
            _, x, y = s.split()[:3]
            pts.append((float(x), float(y)))
    return np.array(pts)


def geo_matrix(coords: np.ndarray) -> np.ndarray:
    """Official TSPLIB GEO distance: PI=3.141592, deg/min -> radians, RRR=6378.388, (int)(RRR*acos(..)+1.0)."""
    PI, RRR = 3.141592, 6378.388
    deg = np.trunc(coords)
    mn = coords - deg
    rad = PI * (deg + 5.0 * mn / 3.0) / 180.0
    lat, lon = rad[:, 0], rad[:, 1]
    q1 = np.cos(lon[:, None] - lon[None, :])
    q2 = np.cos(lat[:, None] - lat[None, :])
    q3 = np.cos(lat[:, None] + lat[None, :])
    arg = np.clip(0.5 * ((1 + q1) * q2 - (1 - q1) * q3), -1.0, 1.0)
    D = np.trunc(RRR * np.arccos(arg) + 1.0)
    np.fill_diagonal(D, 0)
    return D


def held_karp(D: np.ndarray) -> float:
    """Exact closed-tour optimum by DP over subsets (city 0 is the start)."""
    n = len(D)
    m = n - 1
    INF = 1e18
    dp = np.full((1 << m, m), INF)
    for j in range(m):
        dp[1 << j, j] = D[0, j + 1]
    Dm = D[1:, 1:]
    for mask in range(1, 1 << m):
        row = dp[mask]
        if (row >= INF).all():
            continue
        for k in range(m):
            if mask >> k & 1:
                continue
            cand = (row + Dm[:, k]).min()
            nm = mask | (1 << k)
            if cand < dp[nm, k]:
                dp[nm, k] = cand
    return float((dp[(1 << m) - 1] + D[1:, 0]).min())


def all_perms(m: int) -> np.ndarray:
    """All permutations of range(m) in itertools (lexicographic) order."""
    P = np.zeros((1, 0), dtype=np.int8)
    for k in range(1, m + 1):
        blocks = []
        for f in range(k):
            rest = np.array([x for x in range(k) if x != f], dtype=np.int8)
            blocks.append(np.concatenate([np.full((len(P), 1), f, dtype=np.int8), rest[P]], axis=1))
        P = np.concatenate(blocks, axis=0)
    return P


def tour_costs(D: np.ndarray, P: np.ndarray) -> np.ndarray:
    """Closed-tour cost of 0 -> (P+1 order) -> 0 for every permutation row."""
    c = D[0, P[:, 0] + 1].astype(np.float64)
    for i in range(P.shape[1] - 1):
        c += D[P[:, i] + 1, P[:, i + 1] + 1]
    c += D[P[:, -1] + 1, 0]
    return c


def nn_index(D: np.ndarray) -> int:
    """Permutation index (itertools order over cities 1..n-1) of the nearest-neighbour tour from city 0."""
    n = len(D)
    left, cur, tour = set(range(1, n)), 0, []
    while left:
        nxt = min(left, key=lambda j: (D[cur, j], j))
        tour.append(nxt - 1)
        left.remove(nxt)
        cur = nxt
    m, idx, avail = n - 1, 0, list(range(n - 1))
    for pos, c in enumerate(tour):
        r = avail.index(c)
        idx += r * math.factorial(m - 1 - pos)
        avail.pop(r)
    return idx


def run(n_range=range(5, 12), runs=20, out=None, verbose=True) -> dict:
    D = geo_matrix(read_tsp(DATA / "burma14.tsp"))
    warm = "init_index" in inspect.signature(quantum_min_search).parameters
    rows = []
    for n in n_range:
        Dn = D[:n, :n]
        P = all_perms(n - 1)
        N = len(P)
        t = time.perf_counter()
        costs = tour_costs(Dn, P)
        opt = float(costs.min())
        bf_ms = 1000 * (time.perf_counter() - t)
        nn = nn_index(Dn)
        row = {"n": n, "N": N, "qubits": math.ceil(math.log2(N)), "onehot_qubits": n * n, "optimum": opt,
               "nn_cost": float(costs[nn]), "nn_gap_pct": 100 * (float(costs[nn]) / opt - 1),
               "brute_force_ms": bf_ms, "held_karp_states": 2 ** (n - 1) * (n - 1) ** 2}
        for label, kw in (("cold", {}), ("warm", {"init_index": nn})):
            if label == "warm" and not warm:
                continue
            res = [quantum_min_search(costs, seed=s, **kw) for s in range(runs)]
            qt = [r["queries_to_min"] for r in res if r["queries_to_min"] is not None]
            med = float(np.median(qt)) if qt else None
            row[label] = {
                "backend": res[0]["backend"],
                "success_rate": len(qt) / runs,
                "queries_to_min_median": med,
                "queries_to_min_mean": float(np.mean(qt)) if qt else None,
                "coverage_pct_median": med / N * 100 if med is not None else None,
                "ratio_N_over_queries_median": N / med if med else None,
                "budget": res[0]["budget"],
            }
        rows.append(row)
        if verbose:
            print(f"n={n} done", flush=True)
    result = {
        "instance": "burma14 prefixes (first n nodes), closed tour from city 1, TSPLIB GEO distance",
        "warm_start_supported": warm, "runs_per_config": runs, "rows": rows,
        "references": REFERENCES,
        "notes": [
            "The oracle is emulated from classical costs: the full cost array is computed classically; quantum queries are counted, not a reversible cost circuit.",
            "Queries are Grover iterations (+1 per measurement), not wall-clock; simulation time is not comparable to hardware or brute-force time.",
            "Index-register (ceil(log2 N) qubits) and one-hot (n^2 qubits) encodings are different trade-offs: the index register needs a reversible circuit computing tour cost from the index (ancilla/depth not counted); one-hot needs penalty terms.",
            "Success = optimum found within the Durr-Hoyer query budget (22.5*sqrt(N)+1.4*log2(N)^2); once held it is never lost.",
            "For tiny N the query count can be comparable to N, so no advantage over classical enumeration; the sqrt(N) scaling only pays off as N grows.",
            "Backend per row: Qiskit statevector when qubits<=12, exact closed-form Grover statistics otherwise.",
        ]}
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2))
    return result


def table(res: dict) -> str:
    L = ["| n | N | qubits (idx) | n^2 (one-hot) | backend | mode | success | median q | mean q | cov % | N/q | BF ms | HK states |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def f(v, d=1):
        return "-" if v is None else f"{v:.{d}f}"

    for r in res["rows"]:
        for m in ("cold", "warm"):
            if m not in r:
                continue
            c = r[m]
            L.append(f"| {r['n']} | {r['N']} | {r['qubits']} | {r['onehot_qubits']} | {c['backend']} | {m} | "
                     f"{c['success_rate']*100:.0f}% | {f(c['queries_to_min_median'])} | {f(c['queries_to_min_mean'])} | "
                     f"{f(c['coverage_pct_median'], 2)} | {f(c['ratio_N_over_queries_median'])} | "
                     f"{r['brute_force_ms']:.1f} | {r['held_karp_states']} |")
    return "\n".join(L)


def main() -> None:
    res = run(out=ROOT / "results" / "tsplib_benchmark.json")
    print(table(res))


if __name__ == "__main__":
    main()
