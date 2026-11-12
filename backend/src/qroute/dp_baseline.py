"""Stronger classical baseline: exact subset dynamic programming for the min-makespan multi-convoy problem.

Brute force enumerates all N = n!·C(n+k-1,k-1) plans, the same unstructured search Grover accelerates.
Classical algorithms that exploit structure do much better, so an honest comparison must include one:

  1. Held–Karp per convoy v:  tsp_v[S] = cheapest open path from hub v visiting exactly the site set S
                              (2^n · n^2 work per hub).
  2. Min-max combine over subsets:  g_j[S] = min over T ⊆ S of max(tsp_j[T], g_{j-1}[S \\ T])
                              (3^n work per extra hub, by enumerating submasks).

The result is the exact minimum makespan. (The 0.001·total tie-break used elsewhere is ignored here.)
"""

from __future__ import annotations

import time

import numpy as np


def subset_dp_makespan(D: np.ndarray, k: int, n: int, ret: bool = False) -> dict:
    """Points are indexed hubs 0..k-1 then sites k..k+n-1, as in vrp.py."""
    t0 = time.perf_counter()
    inf = float("inf")
    size = 1 << n
    Dss = D[k:k + n, k:k + n]
    tsp = []
    for v in range(k):
        f = np.full((size, n), inf)
        for j in range(n):
            f[1 << j, j] = D[v, k + j]
        for mask in range(1, size):
            for j in range(n):
                if mask >> j & 1:
                    prev = mask ^ (1 << j)
                    if prev:
                        f[mask, j] = (f[prev] + Dss[:, j]).min()
        back = D[k:k + n, v] if ret else np.zeros(n)
        t = (f + back).min(axis=1)
        t[0] = 0.0
        tsp.append(t)
    g = tsp[0].copy()
    states = k * size * n * n
    for v in range(1, k):
        new = np.full(size, inf)
        tv = tsp[v]
        for S in range(size):
            best = inf
            T = S
            while True:
                c = max(tv[T], g[S ^ T])
                if c < best:
                    best = c
                if T == 0:
                    break
                T = (T - 1) & S
            new[S] = best
        g = new
        states += 3 ** n
    return {"makespan_s": float(g[size - 1]), "ms": 1000 * (time.perf_counter() - t0), "states": int(states)}
