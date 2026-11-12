import numpy as np
import pytest

from qroute import vrp
from qroute.dp_baseline import subset_dp_makespan


def random_matrix(m, seed):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 100, (m, 2))
    return np.linalg.norm(pts[:, None] - pts[None], axis=-1)


@pytest.mark.parametrize("k,n,ret", [(1, 5, False), (2, 5, False), (3, 4, False), (2, 4, True)])
def test_subset_dp_matches_exhaustive_minimum_makespan(k, n, ret):
    D = random_matrix(k + n, seed=k * 10 + n)
    best = min(vrp.decode(i, D, k, n, ret)["makespan_s"] for i in range(vrp.num_plans(n, k)))
    assert subset_dp_makespan(D, k, n, ret)["makespan_s"] == pytest.approx(best, rel=1e-9)
