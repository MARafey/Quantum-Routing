"""Three solvers for the relief-convoy multi-stop routing problem on the real OSM road graph.

Problem: start at stop 0 (depot), visit every other stop once, in the order that minimises
total driving time (optionally returning to the depot). Each solver has two phases:

  phase 1  road search  -> travel-time matrix between all stops (+ the road geometry)
  phase 2  visit order  -> best permutation of stops 1..m

  1. Brute force      exhaustive Dijkstra from every stop, one after another; then every one
                      of the m! visit orders is evaluated.
  2. Parallel         stop-bounded Dijkstra from every stop at the same time on a pool of
                      worker processes; then Held–Karp dynamic programming (exact).
  3. Quantum          same parallel road search; then Dürr–Høyer quantum minimum finding
                      (Grover + BBHT) over the m! visit orders, simulated with Qiskit.

Wall-clock times are measured for real. The quantum phase runs on a classical statevector
simulator, so its time says nothing about quantum hardware; the hardware-independent
measure is the number of oracle queries vs. the number of orders evaluated classically.
"""

from __future__ import annotations

import itertools
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from qiskit.quantum_info import Statevector

from .grover_min import grover_circuit
from .roadgraph import RoadGraph

SAMPLE_STRIDE = 20  # keep every 20th settled node for the exploration replay
_G: RoadGraph | None = None


def graph() -> RoadGraph:
    global _G
    if _G is None:
        _G = RoadGraph()
    return _G


def _worker_init() -> None:
    graph()


def _bounded_search(args: tuple[int, list[int]]) -> dict:
    """Worker task: Dijkstra from src, stopping once every other stop is settled."""
    src, targets = args
    g = graph()
    t0 = time.perf_counter()
    r = g.dijkstra(src, set(targets) - {src})
    return {"src": src, "dist": {t: r["dist"][t] for t in targets},
            "paths": {t: g.path(r["parent"], t) for t in targets if t != src},
            "settled": len(r["order"]), "sample": r["order"][::SAMPLE_STRIDE],
            "ms": 1000 * (time.perf_counter() - t0), "pid": os.getpid()}


class Solver:
    def __init__(self, workers: int | None = None) -> None:
        self.g = graph()
        self.workers = workers or min(8, os.cpu_count() or 2)
        self.pool = ProcessPoolExecutor(self.workers, initializer=_worker_init)
        list(self.pool.map(_worker_init_probe, range(self.workers)))  # warm up: every worker loads the graph

    def close(self) -> None:
        self.pool.shutdown(cancel_futures=True)

    # ------------------------------------------------------------------ helpers
    def _coords(self, nodes) -> list[list[float]]:
        return [[round(float(self.g.coords[n][0]), 5), round(float(self.g.coords[n][1]), 5)] for n in nodes]

    @staticmethod
    def tour_cost(D: np.ndarray, perm: tuple[int, ...], ret: bool) -> float:
        seq = (0, *perm) + ((0,) if ret else ())
        return float(sum(D[a, b] for a, b in zip(seq, seq[1:])))

    # ------------------------------------------------------------------ phase 1 variants
    def search_sequential_exhaustive(self, nodes: list[int]) -> tuple[np.ndarray, dict, list[dict]]:
        k = len(nodes)
        D = np.zeros((k, k))
        paths: dict = {}
        searches = []
        for i, s in enumerate(nodes):
            t0 = time.perf_counter()
            r = self.g.dijkstra(s)  # no target: explores the entire road network
            ms = 1000 * (time.perf_counter() - t0)
            for j, t in enumerate(nodes):
                D[i, j] = r["dist"][t]
                if i != j:
                    paths[(i, j)] = self.g.path(r["parent"], t)
            searches.append({"from": i, "settled": len(r["order"]), "ms": ms,
                             "sample": self._coords(r["order"][::SAMPLE_STRIDE])})
        return D, paths, searches

    def search_parallel_bounded(self, nodes: list[int]) -> tuple[np.ndarray, dict, list[dict]]:
        k = len(nodes)
        D = np.zeros((k, k))
        paths: dict = {}
        searches = []
        results = list(self.pool.map(_bounded_search, [(s, nodes) for s in nodes]))
        for i, r in enumerate(results):
            for j, t in enumerate(nodes):
                D[i, j] = r["dist"][t]
                if i != j:
                    paths[(i, j)] = r["paths"][t]
            searches.append({"from": i, "settled": r["settled"], "ms": r["ms"], "worker": r["pid"],
                             "sample": self._coords(r["sample"])})
        return D, paths, searches

    # ------------------------------------------------------------------ phase 2 variants
    def order_brute_force(self, D: np.ndarray, ret: bool) -> dict:
        m = len(D) - 1
        best, best_c, tried = None, math.inf, []
        for perm in itertools.permutations(range(1, m + 1)):
            c = self.tour_cost(D, perm, ret)
            tried.append({"perm": list(perm), "cost": c})
            if c < best_c:
                best, best_c = perm, c
        return {"perm": list(best), "cost": best_c, "evaluated": len(tried), "tried": tried}

    def order_held_karp(self, D: np.ndarray, ret: bool) -> dict:
        m = len(D) - 1
        dp: dict[tuple[int, int], tuple[float, int]] = {}
        states = 0
        for j in range(1, m + 1):
            dp[(1 << j, j)] = (D[0, j], 0)
        for size in range(2, m + 1):
            for subset in itertools.combinations(range(1, m + 1), size):
                mask = sum(1 << x for x in subset)
                for j in subset:
                    prev = mask ^ (1 << j)
                    best = min((dp[(prev, i)][0] + D[i, j], i) for i in subset if i != j)
                    dp[(mask, j)] = best
                    states += 1
        full = sum(1 << x for x in range(1, m + 1))
        end_cost, last = min((dp[(full, j)][0] + (D[j, 0] if ret else 0), j) for j in range(1, m + 1))
        perm, mask = [], full
        while last:
            perm.append(last)
            _, prev = dp[(mask, last)]
            mask ^= 1 << last
            last = prev
        return {"perm": perm[::-1], "cost": float(end_cost), "evaluated": states + m}

    def order_quantum(self, D: np.ndarray, ret: bool, seed: int = 7) -> dict:
        """Dürr–Høyer minimum finding over all visit orders (index register of ceil(log2 m!) qubits)."""
        m = len(D) - 1
        perms = list(itertools.permutations(range(1, m + 1)))
        costs = np.array([self.tour_cost(D, p, ret) for p in perms])  # oracle comparator data (see note)
        N = len(perms)
        if N == 1:
            return {"perm": list(perms[0]), "cost": float(costs[0]), "queries": 0, "qubits": 0, "samples": [],
                    "queries_to_min": 0, "budget": 0, "N": 1}
        n = math.ceil(math.log2(N))
        padded = np.full(2**n, np.inf)
        padded[:N] = costs
        rng = np.random.default_rng(seed)
        budget = 22.5 * math.sqrt(N) + 1.4 * math.log2(N) ** 2
        y = int(rng.integers(N))
        queries, lam, mlim = 0, 6 / 5, 1.0
        samples = [{"q": 0, "perm": list(perms[y]), "cost": float(costs[y]), "improved": True}]
        q_to_min = 0 if costs[y] == costs.min() else None
        while queries < budget:
            marked = padded < padded[y]
            j = int(rng.integers(0, max(1, int(mlim))))
            if marked.any():
                probs = Statevector(grover_circuit(n, marked, j)).probabilities()
                i = int(rng.choice(len(probs), p=probs / probs.sum()))
            else:
                i = int(rng.integers(2**n))  # nothing left to amplify: measurement is uniform
            queries += j + 1
            improved = i < N and padded[i] < padded[y]
            if i < N:
                samples.append({"q": queries, "perm": list(perms[i]), "cost": float(costs[i]), "improved": bool(improved)})
            if improved:
                y, mlim = i, 1.0
                if costs[y] == costs.min() and q_to_min is None:
                    q_to_min = queries
            else:
                mlim = min(lam * mlim, math.sqrt(N))
        return {"perm": list(perms[y]), "cost": float(costs[y]), "queries": queries, "qubits": n, "N": N,
                "samples": samples, "queries_to_min": q_to_min, "budget": budget}

    # ------------------------------------------------------------------ public API
    def solve(self, stops: list[tuple[float, float]], ret: bool = False) -> dict:
        nodes = [self.g.nearest(lat, lon) for lat, lon in stops]
        out: dict = {"stops": [{"node": n, "lat": float(self.g.coords[n][0]), "lon": float(self.g.coords[n][1])}
                               for n in nodes], "return_to_start": ret, "orders": math.factorial(len(nodes) - 1)}

        t0 = time.perf_counter()
        D1, paths, s1 = self.search_sequential_exhaustive(nodes)
        t1 = time.perf_counter()
        o1 = self.order_brute_force(D1, ret)
        t2 = time.perf_counter()
        brute = {"search_ms": 1000 * (t1 - t0), "order_ms": 1000 * (t2 - t1), "searches": s1, "order": o1}

        t0 = time.perf_counter()
        D2, paths2, s2 = self.search_parallel_bounded(nodes)
        t1 = time.perf_counter()
        o2 = self.order_held_karp(D2, ret)
        t2 = time.perf_counter()
        par = {"search_ms": 1000 * (t1 - t0), "order_ms": 1000 * (t2 - t1), "searches": s2, "order": o2,
               "workers": len({s["worker"] for s in s2})}

        t0 = time.perf_counter()
        D3, _, s3 = self.search_parallel_bounded(nodes)
        t1 = time.perf_counter()
        o3 = self.order_quantum(D3, ret)
        t2 = time.perf_counter()
        qu = {"search_ms": 1000 * (t1 - t0), "order_ms": 1000 * (t2 - t1), "searches": s3, "order": o3}

        best = min(o1["cost"], o2["cost"], o3["cost"])
        for res in (brute, par, qu):
            res["total_ms"] = res["search_ms"] + res["order_ms"]
            res["settled"] = sum(s["settled"] for s in res["searches"])
            res["optimal"] = abs(res["order"]["cost"] - best) < 1e-6
        out.update({"brute": brute, "parallel": par, "quantum": qu, "best_cost": best,
                    "legs": {f"{i}-{j}": self._coords(p[::2] + [p[-1]]) for (i, j), p in paths2.items()},
                    "leg_cost": D2.tolist(), "graph_nodes": self.g.n})
        return out


def _worker_init_probe(_: int) -> int:
    return graph().n
