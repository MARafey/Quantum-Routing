import itertools
import math

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from qroute import vrp
from qroute.grover_min import grover_circuit


def test_index_plan_bijection():
    for n, k in [(4, 1), (4, 2), (5, 3)]:
        N = vrp.num_plans(n, k)
        assert N == math.factorial(n) * math.comb(n + k - 1, k - 1)
        seen = set()
        for idx in range(N):
            perm, comp = vrp.decode_index(idx, k, n)
            assert sum(comp) == n and sorted(perm) == list(range(n))
            assert vrp.encode_plan(perm, comp, k, n) == idx
            seen.add((tuple(perm), comp))
        assert len(seen) == N
    assert [tuple(p) for p in vrp.perms(4)] == list(itertools.permutations(range(4)))


def _naive(D, k, n, perm, comp, ret):
    mk = tot = 0.0
    a = 0
    for v in range(k):
        seg = perm[a:a + comp[v]]
        a += comp[v]
        if not seg:
            continue
        t = D[v, k + seg[0]] + sum(D[k + seg[i], k + seg[i + 1]] for i in range(len(seg) - 1))
        if ret:
            t += D[k + seg[-1], v]
        mk, tot = max(mk, t), tot + t
    return mk + 0.001 * tot


@pytest.mark.parametrize("ret", [False, True])
def test_vectorised_costs_match_naive(ret):
    rng = np.random.default_rng(1)
    k, n = 3, 5
    D = rng.uniform(100, 5000, (k + n, k + n))
    np.fill_diagonal(D, 0)
    costs = vrp.evaluate_all(D, k, n, ret)
    assert len(costs) == vrp.num_plans(n, k)
    for idx in rng.integers(len(costs), size=200):
        perm, comp = vrp.decode_index(int(idx), k, n)
        assert costs[idx] == pytest.approx(_naive(D, k, n, perm, comp, ret))
    d = vrp.decode(int(np.argmin(costs)), D, k, n, ret)
    assert d["makespan_s"] + 0.001 * d["total_s"] == pytest.approx(costs.min())


@pytest.mark.parametrize("q,M,j", [(4, 1, 1), (5, 3, 2), (6, 5, 3), (6, 1, 4), (3, 2, 0)])
def test_closed_form_matches_statevector(q, M, j):
    rng = np.random.default_rng(q * 10 + M)
    marked = np.zeros(2**q, dtype=bool)
    marked[rng.choice(2**q, M, replace=False)] = True
    p = Statevector(grover_circuit(q, marked, j)).probabilities()
    assert vrp.grover_p_marked(M, q, j) == pytest.approx(p[marked].sum(), abs=1e-9)


def test_quantum_min_search_finds_optimum():
    rng = np.random.default_rng(3)
    k, n = 2, 4
    D = rng.uniform(100, 5000, (k + n, k + n))
    costs = vrp.evaluate_all(D, k, n, False)
    hits = 0
    for seed in range(10):
        r = vrp.quantum_min_search(costs, seed)
        hits += costs[r["index"]] == costs.min()
        assert r["queries"] >= 0
    assert hits >= 8
    # closed-form backend (forced) also finds it on most seeds
    hits = sum(costs[vrp.quantum_min_search(costs, s, max_qiskit_qubits=0)["index"]] == costs.min()
               for s in range(10))
    assert hits >= 8
