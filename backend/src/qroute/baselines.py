"""Classical references: exact brute force, greedy, and simulated annealing."""

from __future__ import annotations

import itertools
import math
import time

import numpy as np

from .model import Instance, assignment_to_x, energies


def assignment_energy(inst: Instance, assign) -> float:
    x = assignment_to_x(assign, inst.K)
    return float(energies(inst.Q, inst.const, x[None, :])[0])


def brute_force(inst: Instance, batch: int = 50_000) -> dict:
    """Exact optimum over all K^G feasible assignments (vectorised)."""
    t0 = time.perf_counter()
    G, K = len(inst.groups), inst.K
    best_e, best_a, worst_e = math.inf, None, -math.inf
    all_e = []
    it = itertools.product(range(K), repeat=G)
    while True:
        chunk = list(itertools.islice(it, batch))
        if not chunk:
            break
        A = np.array(chunk)
        X = np.zeros((len(A), G * K))
        X[np.arange(len(A))[:, None], np.arange(G) * K + A] = 1
        E = energies(inst.Q, inst.const, X)
        k = int(E.argmin())
        if E[k] < best_e:
            best_e, best_a = float(E[k]), A[k].tolist()
        worst_e = max(worst_e, float(E.max()))
        if K**G <= 100_000:
            all_e.append(E)
    out = {"method": "Exact (brute force)", "assignment": best_a, "energy": best_e,
           "worst_energy": worst_e, "evaluated": K**G, "seconds": time.perf_counter() - t0}
    if all_e:
        out["all_energies"] = np.sort(np.concatenate(all_e))
    return out


def greedy(inst: Instance) -> dict:
    """Largest group first, each picks the option with the least marginal cost."""
    t0 = time.perf_counter()
    G, K = len(inst.groups), inst.K
    order = sorted(range(G), key=lambda g: -inst.groups[g].size)
    x = np.zeros(G * K)
    for g in order:
        best_r, best_e = 0, math.inf
        for r in range(K):
            x[g * K + r] = 1
            e = float(x @ inst.Q @ x)
            x[g * K + r] = 0
            if e < best_e:
                best_r, best_e = r, e
        x[g * K + best_r] = 1
    assign = [int(np.argmax(x[g * K:(g + 1) * K])) for g in range(G)]
    return {"method": "Greedy", "assignment": assign, "energy": assignment_energy(inst, assign),
            "seconds": time.perf_counter() - t0}


def simulated_annealing(inst: Instance, steps: int = 4000, seed: int = 0) -> dict:
    """Single-group-move annealing in the feasible assignment space."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    G, K = len(inst.groups), inst.K
    assign = rng.integers(0, K, G).tolist()
    e = assignment_energy(inst, assign)
    best_a, best_e = assign[:], e
    scale = np.abs(np.diag(inst.Q)).mean()
    for s in range(steps):
        T = scale * (1 - s / steps) + 1e-9
        g = int(rng.integers(G))
        r = int(rng.integers(K))
        if r == assign[g]:
            continue
        old = assign[g]
        assign[g] = r
        e2 = assignment_energy(inst, assign)
        if e2 <= e or rng.random() < math.exp(-(e2 - e) / T):
            e = e2
            if e < best_e:
                best_a, best_e = assign[:], e
        else:
            assign[g] = old
    return {"method": "Simulated annealing", "assignment": best_a, "energy": best_e,
            "seconds": time.perf_counter() - t0}
