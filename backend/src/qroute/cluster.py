"""Scaling QAOA past simulator limits: cluster decomposition with block-coordinate descent.

The full city instance (G groups x K options) is too big for a statevector
simulator. We split groups into clusters of at most ``cluster_size`` groups,
grouping strongly coupled groups together (they share buses/shelters). Each
sweep re-optimises one cluster with XY-QAOA while the other clusters are held
fixed; their choices enter the sub-problem as extra linear terms. A cluster's
new assignment is kept only if the full objective does not get worse.
"""

from __future__ import annotations

import numpy as np

from .baselines import assignment_energy
from .model import Instance
from .qaoa import analyse, run_qaoa


def coupling_matrix(inst: Instance) -> np.ndarray:
    G, K = len(inst.groups), inst.K
    Qs = inst.Q + inst.Q.T
    C = np.zeros((G, G))
    for a in range(G):
        for b in range(G):
            if a != b:
                C[a, b] = np.abs(Qs[a * K:(a + 1) * K, b * K:(b + 1) * K]).sum()
    return C


def make_clusters(inst: Instance, cluster_size: int) -> list[list[int]]:
    """Greedy agglomeration: seed with the most-coupled free group, add its strongest neighbours."""
    C = coupling_matrix(inst)
    free = set(range(len(inst.groups)))
    clusters = []
    while free:
        seed = max(free, key=lambda g: C[g, list(free)].sum())
        cl = [seed]
        free.remove(seed)
        while len(cl) < cluster_size and free:
            nxt = max(free, key=lambda g: C[g, cl].sum())
            cl.append(nxt)
            free.remove(nxt)
        clusters.append(sorted(cl))
    return clusters


def sub_instance(inst: Instance, cluster: list[int], assign: list[int]) -> Instance:
    K = inst.K
    vars_in = [g * K + r for g in cluster for r in range(K)]
    fixed = np.zeros(inst.n)
    for g, r in enumerate(assign):
        if g not in cluster:
            fixed[g * K + r] = 1
    Qs = inst.Q
    sub = Qs[np.ix_(vars_in, vars_in)].copy()
    # Interaction with fixed variables becomes linear: sum_j fixed_j (Q_ij + Q_ji)
    lin = (Qs[vars_in, :] * fixed).sum(axis=1) + (Qs[:, vars_in].T * fixed).sum(axis=1)
    sub[np.diag_indices_from(sub)] += lin
    const = float(fixed @ Qs @ fixed)
    return Instance([inst.groups[g] for g in cluster], [inst.options[g] for g in cluster], K, sub, const,
                    inst.penalty)


def solve_clustered(inst: Instance, init_assign: list[int], cluster_size: int = 4, sweeps: int = 2,
                    reps: int = 2, seed: int = 3) -> dict:
    from .baselines import brute_force

    clusters = make_clusters(inst, cluster_size)
    assign = list(init_assign)
    energy = assignment_energy(inst, assign)
    trace = [{"step": 0, "cluster": None, "energy": energy, "accepted": True}]
    sub_stats = []
    step = 0
    for sweep in range(sweeps):
        for ci, cl in enumerate(clusters):
            step += 1
            sub = sub_instance(inst, cl, assign)
            ref = brute_force(sub)  # exact reference for the sub-problem (for reporting only)
            res = run_qaoa(sub, reps=reps, variant="xy", restarts=2, maxiter=100, seed=seed + step)
            a = analyse(sub, res, ref["energy"], ref["worst_energy"])
            cand = list(assign)
            if a["best_sampled_assignment"] is not None:
                for g, r in zip(cl, a["best_sampled_assignment"]):
                    cand[g] = r
            e = assignment_energy(inst, cand)
            accepted = e <= energy + 1e-9
            if accepted:
                assign, energy = cand, e
            trace.append({"step": step, "sweep": sweep, "cluster": cl, "energy": energy, "accepted": accepted,
                          "p_optimal_sub": a["p_optimal"], "sub_found_optimum": a["found_optimum"]})
            sub_stats.append({"cluster": cl, "qubits": sub.n, "p_feasible": a["p_feasible"],
                              "p_optimal": a["p_optimal"], "approx_ratio": a["approx_ratio"]})
    return {"method": "Clustered XY-QAOA", "assignment": assign, "energy": energy, "clusters": clusters,
            "trace": trace, "sub_stats": sub_stats}
