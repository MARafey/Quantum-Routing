"""How many qubits, how do extra qubits change Dürr–Høyer, and what is the optimal register size?

Experiments A (register padding), B (problem-size sweep), C (circuit resources, real Qiskit).
Run: qroute-qubits  ->  results/qubit_study.json + results/qubit_study.png

Caveat: the DiagonalGate oracle is a stand-in (as in grover_min). A real reversible cost oracle
needs ancilla qubits and a comparator; that overhead is NOT estimated here.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import DiagonalGate
from qiskit.quantum_info import Statevector

from . import pool, vrp
from .grover_min import grover_circuit

RESULTS = Path(__file__).resolve().parents[2] / "results"
MAX_QISKIT = 12


def p_marked(M: int, q: int, j: int) -> float:
    if M <= 0:
        return 0.0
    theta = math.asin(math.sqrt(min(1.0, M / 2**q)))
    return math.sin((2 * j + 1) * theta) ** 2


def grover_probs(marked: np.ndarray, j: int) -> np.ndarray:
    """Exact j-iteration Grover statevector probabilities (oracle sign flip + 2|s><s|-I), numpy.
    Identical to the Qiskit circuit up to global phase (checked in tests); ~1000x faster."""
    a = np.full(len(marked), 1 / math.sqrt(len(marked)))
    for _ in range(j):
        a[marked] *= -1
        a = 2 * a.mean() - a
    return a * a


def padded_search(costs: np.ndarray, q: int, seed: int, sc: np.ndarray | None = None,
                  order: np.ndarray | None = None, max_qiskit: int = MAX_QISKIT, fast: bool = True) -> dict:
    """Dürr–Høyer/BBHT on a q-qubit register for N <= 2**q candidates; indices >= N are never marked.
    The algorithm only knows the register size, so budget and the BBHT cap use N_padded = 2**q."""
    rng = np.random.default_rng(seed)
    N = len(costs)
    size = 2**q
    assert size >= N
    if order is None:
        order = np.argsort(costs, kind="stable")
    if sc is None:
        sc = costs[order]
    true_min = float(sc[0])
    budget = 22.5 * math.sqrt(size) + 1.4 * q**2
    cap = math.sqrt(size)
    real = q <= max_qiskit
    t0 = time.perf_counter()
    y = int(rng.integers(N))
    queries, qtm = 0, (0 if costs[y] == true_min else None)
    lam, m = 6 / 5, 1.0
    while queries < budget:
        j = int(rng.integers(0, max(1, int(m))))
        M = int(np.searchsorted(sc, costs[y], side="left"))
        if M == 0:
            queries += j + 1
            m = min(lam * m, cap)
            continue
        if real:
            marked = np.zeros(size, dtype=bool)
            marked[:N] = costs < costs[y]
            p = grover_probs(marked, j) if fast else Statevector(grover_circuit(q, marked, j)).probabilities()
            i = int(rng.choice(size, p=p / p.sum()))
        elif rng.random() < p_marked(M, q, j):
            i = int(order[rng.integers(M)])
        else:
            while True:
                i = int(rng.integers(size))
                if i >= N or costs[i] >= costs[y]:
                    break
        queries += j + 1
        if i < N and costs[i] < costs[y]:
            y, m = i, 1.0
            if costs[y] == true_min and qtm is None:
                qtm = queries
        else:
            m = min(lam * m, cap)
    return {"correct": bool(costs[y] == true_min), "queries": queries, "queries_to_min": qtm,
            "budget": budget, "ms": 1000 * (time.perf_counter() - t0),
            "backend": ("exact-statevector-numpy" if fast else "qiskit-statevector") if real else "grover-closed-form"}


def make_costs(n: int, k: int, seed: int = 11, ret: bool = False) -> np.ndarray:
    M, _ = pool.pool_matrix("pakistan")
    idx = np.random.default_rng(seed).choice(M.shape[0], size=k + n, replace=False)
    D = np.asarray(M)[np.ix_(idx, idx)]
    import gc
    for attempt in range(20):  # the box is memory-tight when other jobs run: retry on MemoryError
        try:
            return vrp.evaluate_all(D, k, n, ret)
        except MemoryError:
            gc.collect()
            time.sleep(3)
    return vrp.evaluate_all(D, k, n, ret)


def _summ(runs: list[dict]) -> dict:
    qtm = [r["queries_to_min"] for r in runs if r["queries_to_min"] is not None]
    tot = [r["queries"] for r in runs]
    return {"success_rate": sum(r["correct"] for r in runs) / len(runs),
            "median_queries_to_min": float(statistics.median(qtm)) if qtm else None,
            "mean_queries_to_min": float(np.mean(qtm)) if qtm else None,
            "median_total_queries": float(statistics.median(tot)),
            "budget": runs[0]["budget"]}


def experiment_a(seeds: int = 30, instances=((1, 7), (2, 7), (1, 10))) -> list[dict]:
    rows = []
    for k, n in instances:
        costs = make_costs(n, k)
        N = len(costs)
        qmin = max(1, math.ceil(math.log2(N)))
        order = np.argsort(costs, kind="stable")
        sc = costs[order]
        base = None
        for extra in range(5):
            q = qmin + extra
            runs = [padded_search(costs, q, 1000 * extra + s, sc, order) for s in range(seeds)]
            r = {"k": k, "n": n, "N": N, "q_min": qmin, "extra": extra, "q": q, "seeds": seeds,
                 "backend": runs[0]["backend"], **_summ(runs)}
            if base is None:
                base = r["median_queries_to_min"]
            r["qtm_ratio_vs_extra0"] = (r["median_queries_to_min"] / base) if base and r["median_queries_to_min"] else None
            rows.append(r)
            print("A", k, n, extra, r["success_rate"], r["median_queries_to_min"], flush=True)
    return rows


def experiment_b(seeds: int = 20) -> list[dict]:
    rows = []
    for k, ns in ((1, range(4, 11)), (2, range(4, 10))):
        for n in ns:
            costs = make_costs(n, k)
            N = len(costs)
            q = max(1, math.ceil(math.log2(N)))
            order = np.argsort(costs, kind="stable")
            sc = costs[order]
            runs = [padded_search(costs, q, 77 + s, sc, order) for s in range(seeds)]
            s = _summ(runs)
            rows.append({"k": k, "n": n, "N": N, "q": q, "seeds": seeds, "backend": runs[0]["backend"],
                         **s,
                         "N_over_queries_to_min": (N / s["median_queries_to_min"]) if s["median_queries_to_min"] else None,
                         "classical_evals": N,
                         "median_sim_ms_per_run": float(statistics.median(r["ms"] for r in runs))})
            print("B", k, n, N, q, s["success_rate"], s["median_queries_to_min"], flush=True)
    return rows


def experiment_c(qs=range(3, 13)) -> list[dict]:
    basis = ["cx", "rz", "sx", "x"]
    rows = []
    for q in qs:
        rng = np.random.default_rng(q)
        marked = rng.random(2**q) < 0.01
        marked[0] = True
        full = grover_circuit(q, marked, 1)
        t = transpile(full, basis_gates=basis, optimization_level=1, seed_transpiler=1)
        orc = QuantumCircuit(q)
        orc.append(DiagonalGate([-1.0 if m else 1.0 for m in marked]), range(q))
        to = transpile(orc, basis_gates=basis, optimization_level=1, seed_transpiler=1)
        cx = t.count_ops().get("cx", 0)
        cxo = to.count_ops().get("cx", 0)
        rows.append({"q": q, "depth_per_iter": t.depth(), "cx_per_iter": cx,
                     "cx_oracle_standin": cxo, "cx_diffuser": cx - cxo,
                     "total_gates": sum(t.count_ops().values()), "statevector_bytes": 16 * 2**q})
        print("C", q, cx, flush=True)
    return rows


def encodings() -> dict:
    cases = []
    for k, n in ((1, 4), (1, 5), (1, 7), (1, 10), (2, 7), (2, 9)):
        N = vrp.num_plans(n, k)
        cases.append({"k": k, "n": n, "N": N, "index_register_qubits": math.ceil(math.log2(N)),
                      "one_hot_tsp_n2": n * n, "one_hot_tsp_n_minus_1_sq": (n - 1) ** 2})
    return {"cases": cases, "literature": [
        {"source": "arXiv 2212.02735", "claim": "7-node TSP: 31 qubits"},
        {"source": "ICTC 2025 F01-4", "claim": "4 cities: 24 qubits; 5 cities: 56 qubits"}],
        "caveat": "DiagonalGate oracle is a stand-in; a reversible cost oracle needs extra ancilla qubits (not estimated)."}


def conclusions(a, b, c, enc) -> list[str]:
    out = []
    keys = sorted({(r["k"], r["n"]) for r in a})
    best0 = 0
    for key in keys:
        rs = [r for r in a if (r["k"], r["n"]) == key]
        best = min(rs, key=lambda r: r["median_queries_to_min"] or 1e18)
        best0 += best["extra"] == 0
    out.append(f"Optimal register = ceil(log2 N): extra=0 has the lowest median queries_to_min in {best0} of {len(keys)} instances.")
    for key in keys:
        rs = [r for r in a if (r["k"], r["n"]) == key]
        f = [r["qtm_ratio_vs_extra0"] for r in rs if r["extra"] == 4 and r["qtm_ratio_vs_extra0"]]
        if f:
            out.append(f"k={key[0]} n={key[1]} (N={rs[0]['N']}, q_min={rs[0]['q_min']}): +4 qubits -> median queries_to_min x{f[0]:.2f} "
                       f"(~x{f[0] ** 0.25:.2f} per qubit; sqrt2=1.41); success rates for extra 0..4: {[r['success_rate'] for r in rs]}.")
    out.append(f"Problem sweep: min success rate over {len(b)} cases = {min(r['success_rate'] for r in b)}; q ranges {b[0]['q']}..{max(r['q'] for r in b)}.")
    big = max(b, key=lambda r: r["N"])
    out.append(f"Largest case N={big['N']} (q={big['q']}): median queries_to_min={big['median_queries_to_min']} "
               f"vs {big['classical_evals']} classical evaluations (x{big['N_over_queries_to_min']:.0f}).")
    cx = {r["q"]: r["cx_per_iter"] for r in c}
    qs = sorted(cx)
    g = (cx[qs[-1]] / cx[qs[0]]) ** (1 / (qs[-1] - qs[0]))
    out.append(f"CX per Grover iteration grows ~x{g:.2f} per qubit (q={qs[0]}: {cx[qs[0]]}, q={qs[-1]}: {cx[qs[-1]]}), "
               "i.e. ~2^q, dominated by the generic DiagonalGate oracle stand-in; statevector memory 16*2^q bytes doubles per qubit.")
    out.append("Index register (ours) vs one-hot n^2: " + "; ".join(
        f"n={x['n']},k={x['k']}: {x['index_register_qubits']} vs {x['one_hot_tsp_n2']}" for x in enc["cases"])
        + ". Literature: 31 qubits for 7-node TSP, 24/56 for 4/5 cities.")
    out.append("Caveat: the oracle is a diagonal stand-in; a real reversible cost oracle (QRAM + comparator) adds ancilla qubits and depth, not estimated here. "
               "Extra index qubits only pad the search space with unmarked states (no benefit).")
    return out


def plot(a, b, c, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for key in sorted({(r["k"], r["n"]) for r in a}):
        rs = [r for r in a if (r["k"], r["n"]) == key]
        ax[0].plot([r["extra"] for r in rs], [r["median_queries_to_min"] for r in rs], "o-",
                   label=f"k={key[0]} n={key[1]} (N={rs[0]['N']})")
    ax[0].set(xlabel="extra qubits above ceil(log2 N)", ylabel="median queries to min", yscale="log",
              title="A: register padding")
    ax[0].legend(fontsize=7)
    for k, mk in ((1, "o"), (2, "s")):
        rs = [r for r in b if r["k"] == k]
        ax[1].plot([r["q"] for r in rs], [r["median_queries_to_min"] for r in rs], mk + "-", label=f"queries, k={k}")
        ax[1].plot([r["q"] for r in rs], [r["N"] for r in rs], mk + ":", color="gray", label=f"N, k={k}")
    ax[1].set(xlabel="qubits q", yscale="log", title="B: queries vs N")
    ax[1].legend(fontsize=7)
    ax[2].plot([r["q"] for r in c], [r["cx_per_iter"] for r in c], "o-", label="total")
    ax[2].plot([r["q"] for r in c], [r["cx_diffuser"] for r in c], "s--", label="diffuser")
    ax[2].set(xlabel="qubits q", ylabel="CX per Grover iteration", yscale="log", title="C: circuit cost")
    ax[2].legend(fontsize=7)
    for x in ax:
        x.grid(alpha=0.3)
        x.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    a, b, c = experiment_a(), experiment_b(), experiment_c()
    enc = encodings()
    out = {"experiment_A": a, "experiment_B": b, "experiment_C": c, "encodings": enc,
           "conclusions": conclusions(a, b, c, enc)}
    (RESULTS / "qubit_study.json").write_text(json.dumps(out, indent=1))
    plot(a, b, c, RESULTS / "qubit_study.png")
    for s in out["conclusions"]:
        print("-", s)


if __name__ == "__main__":
    main()
