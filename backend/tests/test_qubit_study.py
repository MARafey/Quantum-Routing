import numpy as np

from qroute import qubit_study as qs
from qroute import vrp


def test_padding_finds_optimum_tiny():
    costs = np.random.default_rng(3).random(24)
    for extra in (0,):
        runs = [qs.padded_search(costs, 5 + extra, s, fast=False) for s in range(8)]
        assert sum(r["correct"] for r in runs) >= 7
        assert all(r["backend"] == "qiskit-statevector" for r in runs)


def test_extra0_matches_vrp_statistically():
    costs = np.random.default_rng(4).random(200)
    mine = np.mean([qs.padded_search(costs, 8, s)["correct"] for s in range(12)])
    ref = np.mean([vrp.quantum_min_search(costs, seed=s)["queries_to_min"] is not None for s in range(12)])
    assert mine >= 0.9 and ref >= 0.9


def test_numpy_grover_matches_qiskit():
    from qiskit.quantum_info import Statevector
    from qroute.grover_min import grover_circuit
    marked = np.random.default_rng(5).random(32) < 0.1
    for j in (0, 1, 3):
        ref = Statevector(grover_circuit(5, marked, j)).probabilities()
        assert np.allclose(qs.grover_probs(marked, j), ref, atol=1e-9)
