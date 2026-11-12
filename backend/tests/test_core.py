import numpy as np
from qiskit.quantum_info import Statevector

from qroute import model as M
from qroute.baselines import brute_force
from qroute.network import SHELTERS, build_network
from qroute.qaoa import build_ansatz
from qroute.raptor import Raptor

NET = build_network()


def small_instance(G=2):
    origins = [("Korangi", 60), ("Tower", 50), ("DHA", 40)][:G]
    return M.build_instance(NET, [M.Group(i, o, s, 0) for i, (o, s) in enumerate(origins)], 3)


def test_raptor_journeys_are_consistent():
    r = Raptor(NET)
    res = r.run(NET.stop_by_name("Korangi"), 0, 4)
    for s in SHELTERS:
        for j in r.pareto_journeys(res, NET.stop_by_name(s)):
            assert j.legs[0].from_stop == j.origin and j.legs[-1].to_stop == j.target
            for a, b in zip(j.legs, j.legs[1:]):
                assert a.to_stop == b.from_stop and a.arr <= b.dep  # connected, no time travel
            assert j.arr == j.legs[-1].arr


def test_pareto_more_trips_means_earlier_arrival():
    r = Raptor(NET)
    res = r.run(NET.stop_by_name("Clifton"), 0, 4)
    for s in SHELTERS:
        js = r.pareto_journeys(res, NET.stop_by_name(s))
        for a, b in zip(js, js[1:]):
            assert b.trips > a.trips and b.arr < a.arr


def test_ising_matches_qubo_on_every_bitstring():
    inst = small_instance(2)
    Q, c = M.penalised_qubo(inst)
    op, offset = M.qubo_to_ising(Q, c)
    X = M.all_bitstrings(inst.n)
    E_qubo = M.energies(Q, c, X)
    diag = np.real(op.to_matrix(sparse=True).diagonal()) + offset
    assert np.allclose(diag, E_qubo)


def test_penalty_makes_optimum_feasible():
    inst = small_instance(2)
    Q, c = M.penalised_qubo(inst)
    X = M.all_bitstrings(inst.n)
    best = X[np.argmin(M.energies(Q, c, X))]
    assert M.x_to_assignment(best, inst.K) == brute_force(inst)["assignment"]


def test_xy_mixer_never_leaves_feasible_subspace():
    inst = small_instance(2)
    qc, _, _ = build_ansatz(inst, reps=2, variant="xy")
    bound = qc.assign_parameters(np.random.default_rng(0).uniform(0, 3, qc.num_parameters))
    probs = Statevector(bound).probabilities()
    X = M.all_bitstrings(inst.n)
    feasible = np.array([M.x_to_assignment(x, inst.K) is not None for x in X])
    assert probs[feasible].sum() > 1 - 1e-9
