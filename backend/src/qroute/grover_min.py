"""Dürr–Høyer quantum minimum finding applied to a RAPTOR label scan.

C. Dürr and P. Høyer, "A Quantum Algorithm for Finding the Minimum",
arXiv:quant-ph/9607014 (1996). Uses Grover search with the BBHT schedule for an
unknown number of marked items (Boyer, Brassard, Høyer, Tapp, 1998).

RAPTOR's final step picks the best label among N candidate arrival labels
(every shelter x every round). Classically that is N-1 comparisons. Dürr–Høyer
needs O(sqrt(N)) oracle queries. We count oracle queries (the quantity the
theorem is about), NOT wall-clock time: on a classical simulator the quantum
version is far slower.

Honest caveat: the oracle "is label i < threshold?" is implemented here as a
diagonal phase gate built from the known label array. A real advantage would
need the labels in quantum-accessible memory (QRAM) and a reversible
comparator circuit, which we do not build.
"""

from __future__ import annotations

import math

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import DiagonalGate
from qiskit.quantum_info import Statevector


def grover_circuit(n: int, marked: np.ndarray, iterations: int) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(range(n))
    oracle = DiagonalGate([-1.0 if m else 1.0 for m in marked])
    for _ in range(iterations):
        qc.append(oracle, range(n))
        # Diffusion operator 2|s><s| - I
        qc.h(range(n))
        qc.x(range(n))
        qc.h(n - 1)
        qc.mcx(list(range(n - 1)), n - 1)
        qc.h(n - 1)
        qc.x(range(n))
        qc.h(range(n))
    return qc


def durr_hoyer(values: np.ndarray, rng: np.random.Generator, budget_factor: float = 22.5) -> dict:
    """Return the index found, oracle queries used, and queries until the true min was first held."""
    N = len(values)
    n = max(1, math.ceil(math.log2(N)))
    padded = np.full(2**n, np.inf)
    padded[:N] = values
    true_min = float(np.min(values))
    budget = budget_factor * math.sqrt(N) + 1.4 * math.log2(N) ** 2
    y = int(rng.integers(N))
    queries = 0
    queries_to_min = 0 if values[y] == true_min else None
    lam, m = 6 / 5, 1.0
    trace = [(0, float(values[y]))]
    while queries < budget:
        marked = padded < padded[y]
        if not marked.any():
            # Threshold already at the minimum; the algorithm keeps sampling until the budget ends.
            j = int(rng.integers(0, max(1, int(m))))
            queries += j + 1
            m = min(lam * m, math.sqrt(N))
            continue
        j = int(rng.integers(0, max(1, int(m))))
        probs = Statevector(grover_circuit(n, marked, j)).probabilities()
        i = int(rng.choice(len(probs), p=probs / probs.sum()))
        queries += j + 1  # j Grover iterations + 1 check of the measured index
        if padded[i] < padded[y]:
            y, m = i, 1.0
            trace.append((queries, float(values[y])))
            if values[y] == true_min and queries_to_min is None:
                queries_to_min = queries
        else:
            m = min(lam * m, math.sqrt(N))
    return {"index": y, "value": float(values[y]), "correct": values[y] == true_min,
            "queries": queries, "queries_to_min": queries_to_min, "trace": trace}


def experiment(label_sets: dict[int, np.ndarray], trials: int = 40, seed: int = 5) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for N, vals in label_sets.items():
        runs = [durr_hoyer(vals, rng) for _ in range(trials)]
        q_min = [r["queries_to_min"] for r in runs if r["queries_to_min"] is not None]
        rows.append({
            "N": N, "qubits": math.ceil(math.log2(N)), "classical_comparisons": N - 1,
            "success_rate": sum(r["correct"] for r in runs) / trials,
            "mean_queries_to_min": float(np.mean(q_min)) if q_min else None,
            "median_queries_to_min": float(np.median(q_min)) if q_min else None,
            "sqrtN": math.sqrt(N), "budget": 22.5 * math.sqrt(N) + 1.4 * math.log2(N) ** 2,
            "example_trace": runs[0]["trace"],
        })
    return rows
