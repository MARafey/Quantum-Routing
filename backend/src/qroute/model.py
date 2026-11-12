"""Evacuation assignment model: RAPTOR journey options -> QUBO -> Ising Hamiltonian.

Decision variables
    x[g, r] = 1  if evacuee group g takes journey option r (r < K), else 0.

Objective (minimise)
    sum_g sum_r  n_g * (travel_min[g,r] + TRANSFER_PEN * transfers[g,r]) * x[g,r]     (person-minutes)
  + W_CROWD   * sum_s   (sum_{g,r uses s} n_g x[g,r])^2 / cap_s                          (bus crowding)
  + W_SHELTER * sum_h   (sum_{g,r ends at h} n_g x[g,r])^2 / cap_h                       (shelter load)

Constraint
    sum_r x[g, r] = 1  for every group g  (each group takes exactly one journey)

The two quadratic terms are convex congestion costs: they are the *real* objective
coupling between groups (not just penalty terms), which is what makes the
problem a natural QUBO.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from .network import HEADWAY_MIN, SHELTERS, Network
from .raptor import Journey, Raptor

TRANSFER_PEN = 5.0
W_CROWD = 3.0
W_SHELTER = 3.0
SHELTER_CAP = {"Gulshan": 250, "North Nazimabad": 200, "Malir": 220, "Sohrab Goth": 180, "Jauhar": 200, "Orangi": 160}


@dataclass
class Group:
    id: int
    origin: str
    size: int
    dep: int


@dataclass
class Instance:
    groups: list[Group]
    options: list[list[Journey]]  # options[g][r]
    K: int
    Q: np.ndarray  # upper-triangular QUBO for the objective only (no penalty)
    const: float
    penalty: float

    @property
    def n(self) -> int:
        return len(self.groups) * self.K

    def var(self, g: int, r: int) -> int:
        return g * self.K + r


def generate_options(net: Network, raptor: Raptor, group: Group, K: int) -> list[Journey]:
    """Pick K diverse journey options for a group from RAPTOR Pareto sets."""
    cands: dict[tuple, Journey] = {}
    src = net.stop_by_name(group.origin)
    for dep in (group.dep, group.dep + HEADWAY_MIN, group.dep + 2 * HEADWAY_MIN):
        res = raptor.run(src, dep, max_rounds=4)
        for shelter in SHELTERS:
            for j in raptor.pareto_journeys(res, net.stop_by_name(shelter)):
                j.dep = group.dep  # waiting time counts from the group's ready time
                cands.setdefault(j.signature(), j)
    ranked = sorted(cands.values(), key=lambda j: (j.arr - j.dep) + TRANSFER_PEN * j.transfers)
    chosen: list[Journey] = []
    used_shelters: set[int] = set()
    for j in ranked:  # first pass: diversity in destination shelter
        if len(chosen) < K and j.target not in used_shelters:
            chosen.append(j)
            used_shelters.add(j.target)
    for j in ranked:  # fill remaining slots with next best
        if len(chosen) < K and j not in chosen:
            chosen.append(j)
    return sorted(chosen, key=lambda j: (j.arr - j.dep) + TRANSFER_PEN * j.transfers)


def journey_cost(j: Journey) -> float:
    return (j.arr - j.dep) + TRANSFER_PEN * j.transfers


def build_instance(net: Network, groups: list[Group], K: int = 3) -> Instance:
    raptor = Raptor(net)
    options = [generate_options(net, raptor, g, K) for g in groups]
    G = len(groups)
    n = G * K
    Q = np.zeros((n, n))
    # Linear: person-minutes
    for g, grp in enumerate(groups):
        for r, j in enumerate(options[g]):
            Q[g * K + r, g * K + r] += grp.size * journey_cost(j)
    # Quadratic congestion terms: sum over resources of (sum a_i x_i)^2 / cap
    resources: dict[tuple, tuple[float, list[tuple[int, float]]]] = {}
    for g, grp in enumerate(groups):
        for r, j in enumerate(options[g]):
            i = g * K + r
            for seg in j.segments():
                route, trip, _ = seg
                cap = net.routes[route].capacity[trip]
                resources.setdefault(("seg",) + seg, (W_CROWD / cap, []))[1].append((i, grp.size))
            sname = net.stops[j.target].name
            resources.setdefault(("shelter", sname), (W_SHELTER / SHELTER_CAP[sname], []))[1].append((i, grp.size))
    for _, (w, items) in resources.items():
        for (i, a) in items:
            Q[i, i] += w * a * a  # x^2 = x
        for (i, a), (j, b) in itertools.combinations(items, 2):
            lo, hi = min(i, j), max(i, j)
            Q[lo, hi] += 2 * w * a * b
    # One-hot penalty strength: larger than any single variable's total influence.
    influence = np.abs(Q).sum(axis=0) + np.abs(Q).sum(axis=1)
    penalty = float(1.5 * influence.max())
    return Instance(groups, options, K, Q, 0.0, penalty)


def penalised_qubo(inst: Instance) -> tuple[np.ndarray, float]:
    """Objective + A * sum_g (sum_r x_gr - 1)^2 as an upper-triangular QUBO."""
    Q = inst.Q.copy()
    A = inst.penalty
    for g in range(len(inst.groups)):
        idx = [inst.var(g, r) for r in range(inst.K)]
        for i in idx:
            Q[i, i] -= A
        for i, j in itertools.combinations(idx, 2):
            Q[i, j] += 2 * A
    return Q, inst.const + A * len(inst.groups)


def energies(Q: np.ndarray, const: float, X: np.ndarray) -> np.ndarray:
    """Vectorised QUBO energy for bit matrix X (m x n)."""
    return np.einsum("mi,ij,mj->m", X, Q, X) + const


def all_bitstrings(n: int) -> np.ndarray:
    """Rows = basis states in Qiskit little-endian order: x_i = bit i of the index."""
    idx = np.arange(2**n)[:, None]
    return ((idx >> np.arange(n)) & 1).astype(np.float64)


def qubo_to_ising(Q: np.ndarray, const: float) -> tuple[SparsePauliOp, float]:
    """Map QUBO (x in {0,1}) to Ising (Z eigenvalues) via x_i = (1 - z_i)/2."""
    n = Q.shape[0]
    terms: list[tuple[str, list[int], float]] = []
    offset = const
    h = np.zeros(n)
    for i in range(n):
        offset += Q[i, i] / 2
        h[i] -= Q[i, i] / 2
    for i in range(n):
        for j in range(i + 1, n):
            q = Q[i, j]
            if q == 0:
                continue
            offset += q / 4
            h[i] -= q / 4
            h[j] -= q / 4
            terms.append(("ZZ", [i, j], q / 4))
    terms += [("Z", [i], h[i]) for i in range(n) if h[i] != 0]
    return SparsePauliOp.from_sparse_list(terms, num_qubits=n).simplify(), offset


def assignment_to_x(assign: list[int] | np.ndarray, K: int) -> np.ndarray:
    x = np.zeros(len(assign) * K)
    for g, r in enumerate(assign):
        x[g * K + r] = 1
    return x


def x_to_assignment(x: np.ndarray, K: int) -> list[int] | None:
    G = len(x) // K
    out = []
    for g in range(G):
        row = x[g * K:(g + 1) * K]
        if row.sum() != 1:
            return None
        out.append(int(np.argmax(row)))
    return out
