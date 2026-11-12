import numpy as np

from qroute import pool, vrp


def _D(k, n, seed):
    P = np.random.default_rng(seed).uniform(0, 100, (k + n, 2))
    return np.linalg.norm(P[:, None] - P[None], axis=2)


def test_encode_decode_round_trip():
    for k, n in [(1, 5), (2, 6), (3, 5)]:
        N = vrp.num_plans(n, k)
        for idx in {0, 1, N - 1, N // 2, N // 3, 12345 % N}:
            assert vrp.encode(vrp.decode_index(idx, k, n), k, n) == idx


def test_heuristic_plan_consistent_with_cost_table():
    k, n = 2, 6
    D = _D(k, n, 1)
    costs = vrp.evaluate_all(D, k, n, False)
    h = vrp.classical_heuristic_plan(D, k, n, False)
    assert abs(costs[h["index"]] - h["cost"]) < 1e-9
    assert h["cost"] >= costs.min() and h["evals"] > 0


def test_warm_start_finds_optimum_small_instance():
    k, n = 2, 6
    D = _D(k, n, 2)
    costs = vrp.evaluate_all(D, k, n, False)
    h = vrp.classical_heuristic_plan(D, k, n, False)
    r = vrp.quantum_min_search(costs, 3, init_index=h["index"])
    assert r["queries_to_min"] is not None and abs(r["cost"] - costs.min()) < 1e-9
    # starting from the optimum: zero queries to min
    best = int(np.argmin(costs))
    assert vrp.quantum_min_search(costs, 3, init_index=best)["queries_to_min"] == 0


def test_region_scenarios_valid():
    for rid in pool.REGIONS:
        for seed in range(25):
            s = pool.random_scenario(seed, rid)
            k, n = len(s["hubs"]), len(s["sites"])
            assert 1_500_000 <= vrp.num_plans(n, k) <= 4_000_000
            names = [p["name"] for p in s["hubs"] + s["sites"]]
            assert len(set(names)) == k + n
            if rid == "pakistan":
                continue
            cities = {c[0]: c for c in pool.REGIONS[rid]["cities"]}
            assert all(cities[h["name"]][4] for h in s["hubs"])
            cnt: dict[str, int] = {}
            for p in s["sites"]:
                cnt[cities[p["name"]][3]] = cnt.get(cities[p["name"]][3], 0) + 1
            assert sum(v >= 2 for v in cnt.values()) >= 2
            assert all(pool.in_bbox(rid, p["lat"], p["lon"]) for p in s["hubs"] + s["sites"])
