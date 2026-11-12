"""Figures for the final report, drawn from the result JSON files in backend/results/."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "backend" / "results"
FIG = ROOT / "report" / "figures"
COL = {"brute": "#7c5e3c", "parallel": "#0b7a69", "dp": "#8a8f98", "quantum": "#3451c6", "ws": "#8a63d2"}
REGION_LABEL = {"pakistan": "Pakistan\n2 hubs · 9 sites", "turkiye-syria": "Türkiye–Syria\n1 hub · 10 sites",
                "bengal-floods": "Bengal\n3 hubs · 8 sites", "nepal-himalaya": "Nepal–India\n3 hubs · 8 sites"}


def load(name: str):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", color="#e2e5e9", lw=0.6)
    ax.set_axisbelow(True)


def dp_steps(n: int, k: int) -> float:
    return k * 2**n * n**2 + (k - 1) * 3**n


def num_plans(n: int, k: int) -> float:
    return math.factorial(n) * math.comb(n + k - 1, k - 1)


def grover_constant() -> float:
    rows = [r for r in load("qubit_study.json")["experiment_B"] if r["q"] >= 13]
    cs = sorted(r["median_queries_to_min"] / math.sqrt(r["N"]) for r in rows)
    return cs[len(cs) // 2]


def crossover(k: int, c: float) -> int:
    return next(n for n in range(4, 60) if dp_steps(n, k) < c * math.sqrt(num_plans(n, k)))


def fig_coverage(path: Path) -> None:
    rows = load("region_runs.json")["rows"]
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    series = [("brute", "Brute force", lambda r: r["methods"]["brute"]["coverage_pct"]),
              ("parallel", "Parallel (8 workers)", lambda r: r["methods"]["parallel"]["coverage_pct"]),
              ("dp", "Subset DP (exact classical)", lambda r: 100 * r["subset_dp"]["states"] / r["N"]),
              ("quantum", "Quantum search", lambda r: r["methods"]["quantum"]["coverage_pct"]),
              ("ws", "Quantum + warm start", lambda r: r["methods"]["quantum_ws"]["coverage_pct"])]
    w = 0.16
    for i, (key, label, fn) in enumerate(series):
        xs = [j + (i - 2) * w for j in range(len(rows))]
        ys = [fn(r) for r in rows]
        ax.bar(xs, ys, w, color=COL[key], label=label)
        for x, y in zip(xs, ys):
            ax.text(x, y * 1.15, f"{y:.3g}", ha="center", va="bottom", fontsize=5.8, rotation=90)
    ax.set_yscale("log")
    ax.set_ylim(0.004, 600)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([REGION_LABEL[r["region"]] for r in rows], fontsize=8)
    ax.set_ylabel("share of N plans examined (%, log)", fontsize=8)
    ax.legend(fontsize=7, ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.22))
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_scaling(path: Path) -> None:
    c = grover_constant()
    B = load("qubit_study.json")["experiment_B"]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    ax = axs[0]
    for k, mk in ((1, "o"), (2, "s")):
        rs = [r for r in B if r["k"] == k]
        ax.plot([r["N"] for r in rs], [r["median_queries_to_min"] for r in rs], mk + "-", color=COL["quantum"],
                ms=4, lw=1.2, alpha=1 if k == 1 else 0.55, label=f"Grover queries, k={k} (measured)")
    ns = [10**(i / 4) for i in range(4, 28)]
    ax.plot(ns, ns, "--", color=COL["brute"], lw=1.2, label="Exhaustive search: N")
    ax.plot(ns, [c * math.sqrt(x) for x in ns], ":", color=COL["quantum"], lw=1.2, label=f"{c:.2f}·√N fit")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("number of plans N", fontsize=8); ax.set_ylabel("queries / evaluations", fontsize=8)
    ax.set_title("Measured on real OSRM instances", fontsize=8.5)
    ax.legend(fontsize=6.3, frameon=False, loc="upper left"); _style(ax)
    ax = axs[1]
    k = 2
    nn = list(range(4, 25))
    ax.plot(nn, [num_plans(n, k) for n in nn], color=COL["brute"], lw=1.4, label="Exhaustive N")
    ax.plot(nn, [dp_steps(n, k) for n in nn], color=COL["dp"], lw=1.4, label="Subset DP steps")
    ax.plot(nn, [c * math.sqrt(num_plans(n, k)) for n in nn], color=COL["quantum"], lw=1.4, label="Grover queries (c·√N)")
    x = crossover(k, c)
    ax.axvline(x, color="#d9480f", lw=0.9, ls="--")
    ax.text(x + 0.3, 3e2, f"DP wins from\nn = {x} sites", fontsize=7, color="#d9480f")
    ax.set_yscale("log"); ax.set_xlabel("number of sites n (k = 2 convoys)", fontsize=8)
    ax.set_title("Operation counts, extrapolated", fontsize=8.5)
    ax.legend(fontsize=6.5, frameon=False, loc="upper left"); _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_warmstart(path: Path) -> None:
    S = load("quantum_warmstart_benchmark.json")["summary"]
    regs = list(S)
    names = {"pakistan": "Pakistan", "turkiye-syria": "Türkiye–Syria", "bengal-floods": "Bengal", "nepal-himalaya": "Nepal–India"}
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    w = 0.34
    for i, (key, label, col) in enumerate((("standard", "Standard Dürr–Høyer", COL["quantum"]), ("warm", "Warm-started (incl. heuristic work)", COL["ws"]))):
        ys = [S[r][key]["median_coverage_pct"] for r in regs]
        xs = [j + (i - 0.5) * w for j in range(len(regs))]
        ax.bar(xs, ys, w, color=col, label=label)
        for x, y in zip(xs, ys):
            ax.text(x, y * 1.1, f"{y:.3f}%", ha="center", fontsize=6.5)
    ax.set_yscale("log"); ax.set_ylim(0.003, 0.5)
    ax.set_xticks(range(len(regs)))
    ax.set_xticklabels([f"{names[r]}\nheuristic optimal: {S[r]['heuristic_found_optimum_pct']:.0f}%" for r in regs], fontsize=7.5)
    ax.set_ylabel("median share of plans examined (%)", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper right"); _style(ax)
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


def fig_tsplib(path: Path) -> None:
    T = load("tsplib_benchmark.json")["rows"]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9))
    ax = axs[0]
    cold = [(r["N"], r["cold"]["ratio_N_over_queries_median"]) for r in T if r["cold"]["ratio_N_over_queries_median"]]
    warm = [(r["N"], r["warm"]["ratio_N_over_queries_median"]) for r in T if r.get("warm") and r["warm"]["ratio_N_over_queries_median"]]
    ax.plot(*zip(*cold), "o-", color=COL["quantum"], ms=4, label="cold start")
    ax.plot(*zip(*warm), "s--", color=COL["ws"], ms=4, label="nearest-neighbour warm start")
    ax.axhline(1, color="#7b8592", lw=0.8)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("tours N = (n−1)!", fontsize=8)
    ax.set_ylabel("N ÷ queries to optimum", fontsize=8); ax.set_title("burma14 prefixes: reduction vs exhaustive", fontsize=8.5)
    ax.legend(fontsize=7, frameon=False); _style(ax)
    ax = axs[1]
    n = [r["n"] for r in T]
    ax.plot(n, [r["qubits"] for r in T], "o-", color=COL["quantum"], ms=4, label="index register ⌈log₂N⌉")
    ax.plot(n, [r["onehot_qubits"] for r in T], "s-", color=COL["brute"], ms=4, label="one-hot n²")
    ax.set_xlabel("cities n", fontsize=8); ax.set_ylabel("qubits", fontsize=8); ax.set_title("Qubits for the same tours", fontsize=8.5)
    ax.legend(fontsize=7, frameon=False); _style(ax)
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


def build_all() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_coverage(FIG / "fig_coverage.png")
    fig_scaling(FIG / "fig_scaling.png")
    fig_warmstart(FIG / "fig_warmstart.png")
    fig_tsplib(FIG / "fig_tsplib.png")


if __name__ == "__main__":
    build_all()
    print("figures written to", FIG)
