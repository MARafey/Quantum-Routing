from qroute import pool, vrp


def test_random_scenarios_valid():
    for seed in range(60):
        s = pool.random_scenario(seed)
        k, n = len(s["hubs"]), len(s["sites"])
        N = vrp.num_plans(n, k)
        assert 1_500_000 <= N <= 4_000_000
        hubs = {h["name"] for h in s["hubs"]}
        sites = [x["name"] for x in s["sites"]]
        assert len(hubs) == k and len(set(sites)) == n
        assert not hubs & set(sites)
        assert all(pool.CITIES[pool.INDEX[h]][4] for h in hubs)
        assert len({pool.CITIES[pool.INDEX[h]][3] for h in hubs}) == k
        idx = [pool.INDEX[x] for x in sites]
        lats = [pool.CITIES[i][1] for i in idx]
        lons = [pool.CITIES[i][2] for i in idx]
        assert max(lats) - min(lats) > 4 or max(lons) - min(lons) > 4
        assert len({pool.CITIES[i][3] for i in idx}) >= 3


def test_random_scenario_deterministic():
    assert pool.random_scenario(3) == pool.random_scenario(3)
