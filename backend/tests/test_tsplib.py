from qroute.tsplib_bench import DATA, all_perms, geo_matrix, held_karp, nn_index, read_tsp, tour_costs
from qroute.vrp import quantum_min_search


def test_geo_held_karp_burma14():
    D = geo_matrix(read_tsp(DATA / "burma14.tsp"))
    assert D.shape == (14, 14) and (D == D.T).all()
    assert held_karp(D) == 3323


def test_geo_held_karp_ulysses16():
    D = geo_matrix(read_tsp(DATA / "ulysses16.tsp"))
    assert held_karp(D) == 6859


def test_perms_and_bruteforce_match_held_karp():
    D = geo_matrix(read_tsp(DATA / "burma14.tsp"))[:8, :8]
    assert tour_costs(D, all_perms(7)).min() == held_karp(D)
    assert 0 <= nn_index(D) < 5040


def test_quantum_finds_optimum_n6():
    D = geo_matrix(read_tsp(DATA / "burma14.tsp"))[:6, :6]
    c = tour_costs(D, all_perms(5))
    ok = sum(quantum_min_search(c, seed=s)["queries_to_min"] is not None for s in range(10))
    assert ok >= 8
