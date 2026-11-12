import itertools

import numpy as np

from qroute.solvers import Solver


def random_matrix(k, seed):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 100, (k, 2))
    return np.linalg.norm(pts[:, None] - pts[None], axis=-1)


def test_held_karp_matches_brute_force():
    for seed in range(5):
        for ret in (False, True):
            D = random_matrix(6, seed)
            bf = Solver.order_brute_force(Solver, D, ret)
            hk = Solver.order_held_karp(Solver, D, ret)
            assert abs(bf["cost"] - hk["cost"]) < 1e-9
            assert abs(Solver.tour_cost(D, tuple(hk["perm"]), ret) - hk["cost"]) < 1e-9


def test_quantum_order_is_a_valid_permutation_and_usually_optimal():
    hits = 0
    for seed in range(5):
        D = random_matrix(5, seed)
        q = Solver.order_quantum(Solver, D, False, seed=seed)
        assert sorted(q["perm"]) == [1, 2, 3, 4]
        assert q["qubits"] == 5  # 4! = 24 orders -> 5-qubit index register
        best = min(Solver.tour_cost(D, p, False) for p in itertools.permutations(range(1, 5)))
        hits += abs(q["cost"] - best) < 1e-9
    assert hits >= 4  # Dürr–Høyer succeeds with high probability within its query budget
