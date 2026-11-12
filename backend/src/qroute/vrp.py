"""Multi-convoy routing: k depots (one convoy each), n sites, objective = makespan + 0.001*total.

A plan = (permutation of the n sites, composition of n into k ordered non-negative parts);
convoy v takes the next c_v sites of the permutation.  N = n! * C(n+k-1, k-1).
Points are indexed depots 0..k-1, sites k..k+n-1.
"""

from __future__ import annotations

import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

import numpy as np
from qiskit.quantum_info import Statevector

from .grover_min import grover_circuit

TIE = 0.001
BLOCK = 120_000  # permutations per vectorised block


def num_plans(n: int, k: int) -> int:
    return math.factorial(n) * math.comb(n + k - 1, k - 1)


@lru_cache(maxsize=None)
def compositions(n: int, k: int) -> np.ndarray:
    out: list[tuple[int, ...]] = []

    def rec(left: int, parts: int, cur: tuple[int, ...]) -> None:
        if parts == 1:
            out.append(cur + (left,))
            return
        for c in range(left + 1):
            rec(left - c, parts - 1, cur + (c,))

    rec(n, k, ())
    return np.array(out, dtype=np.int16)


@lru_cache(maxsize=None)
def perms(n: int) -> np.ndarray:
    """All permutations of range(n) as an int8 array, in itertools.permutations (lexicographic) order."""
    if n == 1:
        return np.zeros((1, 1), dtype=np.int8)
    base = perms(n - 1)
    blocks = []
    for f in range(n):
        rest = base + (base >= f).astype(np.int8)
        blocks.append(np.concatenate([np.full((len(base), 1), f, dtype=np.int8), rest], axis=1))
    return np.concatenate(blocks, axis=0)


def unrank_perm(rank: int, n: int) -> list[int]:
    items = list(range(n))
    out = []
    for i in range(n, 0, -1):
        f = math.factorial(i - 1)
        out.append(items.pop(rank // f))
        rank %= f
    return out


def decode_index(index: int, k: int, n: int) -> tuple[list[int], tuple[int, ...]]:
    C = len(compositions(n, k))
    pr, cr = divmod(int(index), C)
    return unrank_perm(pr, n), tuple(int(x) for x in compositions(n, k)[cr])


def encode_plan(perm: list[int], comp: tuple[int, ...], k: int, n: int) -> int:
    rank, items = 0, list(range(n))
    for i, p in enumerate(perm):
        rank += items.index(p) * math.factorial(n - 1 - i)
        items.remove(p)
    cr = [tuple(int(x) for x in c) for c in compositions(n, k)].index(tuple(comp))
    return rank * len(compositions(n, k)) + cr


def decode(index: int, D: np.ndarray, k: int, n: int, ret: bool = False) -> dict:
    perm, comp = decode_index(index, k, n)
    routes, a = [], 0
    for v in range(k):
        routes.append([v] + [k + s for s in perm[a:a + comp[v]]])
        a += comp[v]
    times = []
    for r in routes:
        t = sum(D[r[i], r[i + 1]] for i in range(len(r) - 1))
        if ret and len(r) > 1:
            t += D[r[-1], r[0]]
        times.append(float(t))
    return {"routes": routes, "makespan_s": max(times), "total_s": sum(times)}


def block_costs(D: np.ndarray, k: int, n: int, ret: bool, pm: np.ndarray) -> np.ndarray:
    """Costs (P x C) of every plan for a block of permutations, vectorised over permutations."""
    P = pm.shape[0]
    sites = pm.astype(np.intp) + k
    cum = np.zeros((P, n))
    if n > 1:
        cum[:, 1:] = np.cumsum(D[sites[:, :-1], sites[:, 1:]], axis=1)
    start = [[D[v, sites[:, a]] for a in range(n)] for v in range(k)]
    end = [[D[sites[:, b], v] for b in range(n)] for v in range(k)] if ret else None
    comps = compositions(n, k)
    out = np.empty((P, len(comps)))
    for ci, c in enumerate(comps):
        mk, tot, a = np.zeros(P), np.zeros(P), 0
        for v in range(k):
            b = a + int(c[v])
            if b > a:  # empty segment costs 0
                seg = start[v][a] + cum[:, b - 1] - cum[:, a]
                if ret:
                    seg = seg + end[v][b - 1]
                mk = np.maximum(mk, seg)
                tot += seg
            a = b
        out[:, ci] = mk + TIE * tot
    return out


def evaluate_all(D: np.ndarray, k: int, n: int, ret: bool) -> np.ndarray:
    pm = perms(n)
    return np.concatenate([block_costs(D, k, n, ret, pm[s:s + BLOCK]).reshape(-1)
                           for s in range(0, len(pm), BLOCK)])


def _block_min(D, k, n, ret, s, e):
    pm = perms(n)
    C = len(compositions(n, k))
    best, bi = math.inf, -1
    for a in range(s, e, BLOCK):
        c = block_costs(D, k, n, ret, pm[a:min(a + BLOCK, e)])
        i = int(np.argmin(c))
        if c.flat[i] < best:
            best, bi = float(c.flat[i]), a * C + i
    return best, bi


def _noop(x):
    return x


def make_pool(workers: int | None = None) -> ProcessPoolExecutor:
    w = workers or min(8, os.cpu_count() or 1)
    pool = ProcessPoolExecutor(max_workers=w)
    list(pool.map(_noop, range(w * 4)))  # spawn workers + import this module now
    pool._qr_workers = w  # type: ignore[attr-defined]
    return pool


def brute_force(D, k, n, ret=False) -> dict:
    t0 = time.perf_counter()
    best, bi = _block_min(D, k, n, ret, 0, math.factorial(n))
    ms = 1000 * (time.perf_counter() - t0)
    return {"ms": ms, "evaluated": num_plans(n, k), "index": bi, "cost": best}


def parallel_brute_force(D, k, n, ret, pool: ProcessPoolExecutor) -> dict:
    w = getattr(pool, "_qr_workers", 4)
    nf = math.factorial(n)
    step = max(1, math.ceil(nf / (w * 4)))
    t0 = time.perf_counter()
    futs = [pool.submit(_block_min, D, k, n, ret, s, min(s + step, nf)) for s in range(0, nf, step)]
    best, bi = min(f.result() for f in futs)
    ms = 1000 * (time.perf_counter() - t0)
    return {"ms": ms, "evaluated": num_plans(n, k), "index": bi, "cost": best, "workers": w}


def grover_p_marked(M: int, q: int, j: int) -> float:
    if M <= 0:
        return 0.0
    theta = math.asin(math.sqrt(min(1.0, M / 2**q)))
    return math.sin((2 * j + 1) * theta) ** 2


def quantum_min_search(costs: np.ndarray, seed: int = 7, max_qiskit_qubits: int = 12) -> dict:
    """Dürr–Høyer minimum finding with the BBHT schedule (lambda=6/5)."""
    rng = np.random.default_rng(seed)
    N = len(costs)
    q = max(1, math.ceil(math.log2(N)))
    size = 2**q
    t0 = time.perf_counter()
    order = np.argsort(costs, kind="stable")
    sc = costs[order]
    true_min = float(sc[0])
    budget = 22.5 * math.sqrt(N) + 1.4 * math.log2(N) ** 2
    real = q <= max_qiskit_qubits
    y = int(rng.integers(N))
    queries, qtm = 0, (0 if costs[y] == true_min else None)
    lam, m = 6 / 5, 1.0
    log = [(0, y, True)]
    while queries < budget:
        j = int(rng.integers(0, max(1, int(m))))
        M = int(np.searchsorted(sc, costs[y], side="left"))  # strictly better than the threshold
        if M == 0:  # holding the minimum: remaining runs can never improve, only burn queries
            queries += j + 1
            m = min(lam * m, math.sqrt(N))
            continue
        if real:
            marked = np.zeros(size, dtype=bool)
            marked[:N] = costs < costs[y]
            p = Statevector(grover_circuit(q, marked, j)).probabilities()
            i = int(rng.choice(size, p=p / p.sum()))
        elif rng.random() < grover_p_marked(M, q, j):
            i = int(order[rng.integers(M)])
        else:  # uniform over the unmarked indices of the 2**q register (incl. padding)
            while True:
                i = int(rng.integers(size))
                if i >= N or costs[i] >= costs[y]:
                    break
        queries += j + 1
        imp = bool(i < N and costs[i] < costs[y])
        if imp:
            y, m = i, 1.0
            if costs[y] == true_min and qtm is None:
                qtm = queries
        else:
            m = min(lam * m, math.sqrt(N))
        log.append((queries, i, imp))
    ms = 1000 * (time.perf_counter() - t0)
    if len(log) > 400:
        keep = {t for t, e in enumerate(log) if e[2]}
        rest = [t for t in range(len(log)) if t not in keep]
        room = max(0, 400 - len(keep))
        if room and rest:
            keep |= {rest[int(x)] for x in np.linspace(0, len(rest) - 1, room)}
        log = [log[t] for t in sorted(keep)][:400]
    samples = [{"q": a, "index": b, "cost_s": float(costs[b]) if b < N else None, "improved": c}
               for a, b, c in log]
    return {"ms": ms, "queries": queries, "queries_to_min": qtm, "budget": budget, "qubits": q,
            "backend": "qiskit-statevector" if real else "grover-closed-form",
            "samples": samples, "index": y, "cost": float(costs[y])}


def held_karp_states(n: int, k: int = 1) -> int | None:
    return 2**n * n**2 if k == 1 else None


def scaling(k: int, measured: list[dict]) -> list[dict]:
    """measured: dicts with N, queries_to_min, evals_per_s (from brute force)."""
    cs = [m["queries_to_min"] / math.sqrt(m["N"]) for m in measured if m.get("queries_to_min")]
    c = float(np.mean(cs)) if cs else 1.0
    eps = [m["evals_per_s"] for m in measured if m.get("evals_per_s")]
    rate = float(np.mean(eps)) if eps else 1e6
    rows = []
    for n in range(4, 21):
        N = num_plans(n, k)
        gq = c * math.sqrt(N)
        t = N / rate
        rows.append({"n": n, "N": N, "brute_evals": N, "heldkarp_states": held_karp_states(n, k),
                     "grover_queries": gq, "brute_time_s_projected": t,
                     "break_even_us_projected": t * 1e6 / gq})
    return rows
