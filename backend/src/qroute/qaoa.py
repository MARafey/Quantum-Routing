"""QAOA for the evacuation assignment QUBO, in two variants.

* ``penalty``: textbook QAOA (Farhi et al., 2014). |+>^n start, transverse-field
  RX mixer, one-hot constraint enforced by a quadratic penalty in the cost.
* ``xy``: constraint-preserving QAOA (Hadfield et al., "From the Quantum
  Approximate Optimization Algorithm to a Quantum Alternating Operator Ansatz",
  Algorithms 2019). Each group's K qubits start in a W state (one-hot
  superposition) and the mixer is a ring of XX+YY gates, which conserves
  Hamming weight. The search never leaves the feasible subspace, so no penalty
  term is needed.

Circuits are built once with symbolic parameters, transpiled once, then bound
for each optimiser step. Training uses exact statevector simulation; final
results are sampled with shots on Qiskit Aer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import ParameterVector
from qiskit.circuit.library import PauliEvolutionGate, StatePreparation, XXPlusYYGate
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from scipy.optimize import minimize

from .model import Instance, all_bitstrings, energies, penalised_qubo, qubo_to_ising, x_to_assignment


def w_state(k: int) -> StatePreparation:
    amp = np.zeros(2**k)
    for i in range(k):
        amp[1 << i] = 1 / np.sqrt(k)
    return StatePreparation(amp, label=f"W{k}")


def build_ansatz(inst: Instance, reps: int, variant: str) -> tuple[QuantumCircuit, float, float]:
    """Return (parametrised circuit, energy scale, ising offset)."""
    if variant == "penalty":
        Q, c = penalised_qubo(inst)
    else:
        Q, c = inst.Q, inst.const
    scale = float(np.abs(Q).max())
    cost_op, _ = qubo_to_ising(Q / scale, c / scale)
    n, K, G = inst.n, inst.K, len(inst.groups)
    gammas = ParameterVector("γ", reps)
    betas = ParameterVector("β", reps)
    qc = QuantumCircuit(n)
    if variant == "penalty":
        qc.h(range(n))
    else:
        for g in range(G):
            qc.append(w_state(K), [g * K + r for r in range(K)])
    for p in range(reps):
        qc.append(PauliEvolutionGate(cost_op, time=gammas[p]), range(n))
        if variant == "penalty":
            qc.rx(2 * betas[p], range(n))
        else:
            pairs = [(r, (r + 1) % K) for r in range(K)] if K > 2 else [(0, 1)]
            for g in range(G):
                for a, b in pairs:
                    qc.append(XXPlusYYGate(2 * betas[p]), [g * K + a, g * K + b])
    return qc, scale, c


@dataclass
class QAOAResult:
    variant: str
    reps: int
    best_params: list[float]
    history: list[float] = field(default_factory=list)
    counts: dict[int, int] = field(default_factory=dict)
    shots: int = 0
    seconds: float = 0.0
    circuit_depth: int = 0
    two_qubit_gates: int = 0
    num_qubits: int = 0
    evaluations: int = 0


def run_qaoa(inst: Instance, reps: int = 2, variant: str = "xy", restarts: int = 4, maxiter: int = 150,
             shots: int = 4096, seed: int = 11, cvar_alpha: float = 0.2) -> QAOAResult:
    """Train QAOA angles with COBYLA, then sample on Aer.

    The training loss is CVaR_alpha of the energy distribution (Barkoutsos et al.,
    "Improving Variational Quantum Optimization using CVaR", Quantum 4, 256, 2020):
    the mean energy of the best ``alpha`` fraction of outcomes. alpha=1 gives the
    plain expectation value. CVaR rewards concentrating probability on good
    solutions, which is what we sample at the end.
    """
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    qc, _, _ = build_ansatz(inst, reps, variant)
    sim = AerSimulator(seed_simulator=seed)
    tqc = transpile(qc, basis_gates=["rz", "sx", "x", "cx", "ry", "rx", "h"], optimization_level=1, seed_transpiler=seed)
    params = list(qc.parameters)  # sorted: β..., γ...
    # Training objective: expected (scaled) QUBO energy of the variant's cost function.
    X = all_bitstrings(inst.n)
    if variant == "penalty":
        Qp, cp = penalised_qubo(inst)
        E = energies(Qp, cp, X)
    else:
        E = energies(inst.Q, inst.const, X)
    E = E / np.abs(E).max()
    order = np.argsort(E)
    E_sorted = E[order]

    evals = 0
    history: list[float] = []

    def objective(theta: np.ndarray) -> float:
        nonlocal evals
        evals += 1
        bound = tqc.assign_parameters(dict(zip(params, theta)))
        probs = Statevector(bound).probabilities()[order]
        if cvar_alpha >= 1:
            val = float(probs @ E_sorted)
        else:
            cum = np.cumsum(probs)
            w = np.clip(cvar_alpha - (cum - probs), 0, probs)  # mass of each state inside the alpha-tail
            val = float(w @ E_sorted / cvar_alpha)
        history.append(val)
        return val

    best = None
    best_hist: list[float] = []
    for _ in range(restarts):
        history = []
        x0 = rng.uniform(0, np.pi, len(params))
        res = minimize(objective, x0, method="COBYLA", options={"maxiter": maxiter, "rhobeg": 0.4})
        if best is None or res.fun < best.fun:
            best, best_hist = res, history[:]
    # Final sampling with shots on the Aer simulator.
    bound = tqc.assign_parameters(dict(zip(params, best.x)))
    meas = bound.copy()
    meas.measure_all()
    counts_str = sim.run(meas, shots=shots).result().get_counts()
    counts = {int(k.replace(" ", ""), 2): v for k, v in counts_str.items()}
    ops = tqc.count_ops()
    return QAOAResult(variant, reps, best.x.tolist(), best_hist, counts, shots, time.perf_counter() - t0,
                      tqc.depth(), int(ops.get("cx", 0)), inst.n, evals)


def analyse(inst: Instance, res: QAOAResult, exact_energy: float, worst_energy: float) -> dict:
    """Interpret QAOA samples: feasibility, optimality, approximation ratio."""
    n, K = inst.n, inst.K
    feasible_shots = opt_shots = 0
    exp_feas = 0.0
    best_sample_e, best_sample_a = np.inf, None
    rows = []
    for b, c in sorted(res.counts.items(), key=lambda kv: -kv[1]):
        x = np.array([(b >> i) & 1 for i in range(n)], dtype=float)
        a = x_to_assignment(x, K)
        e = float(energies(inst.Q, inst.const, x[None, :])[0]) if a is not None else None
        if a is not None:
            feasible_shots += c
            exp_feas += c * e
            if abs(e - exact_energy) < 1e-6:
                opt_shots += c
            if e < best_sample_e:
                best_sample_e, best_sample_a = e, a
        if len(rows) < 12:
            rows.append({"bitstring": format(b, f"0{n}b"), "count": c, "assignment": a, "energy": e})
    shots = res.shots
    most_likely_feasible = next((r for r in rows if r["assignment"] is not None), None)
    exp_feas = exp_feas / feasible_shots if feasible_shots else None
    span = worst_energy - exact_energy
    approx = (worst_energy - exp_feas) / span if (exp_feas is not None and span > 0) else None
    return {
        "variant": res.variant, "reps": res.reps, "num_qubits": res.num_qubits,
        "p_feasible": feasible_shots / shots, "p_optimal": opt_shots / shots,
        "expected_feasible_energy": exp_feas, "approx_ratio": approx,
        "best_sampled_energy": best_sample_e if best_sample_a else None,
        "best_sampled_assignment": best_sample_a,
        "found_optimum": best_sample_a is not None and abs(best_sample_e - exact_energy) < 1e-6,
        "most_likely_feasible": most_likely_feasible,
        "top_samples": rows, "history": res.history, "seconds": res.seconds,
        "circuit_depth": res.circuit_depth, "cx_count": res.two_qubit_gates,
        "evaluations": res.evaluations, "shots": shots,
    }
