"""Generate the hackathon report (.docx) with figures from backend/results/results.json.

Usage: uv run qroute-report
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "backend" / "results" / "results.json"
OUT_DIR = ROOT / "report"
FIG = OUT_DIR / "figures"


# ---------------------------------------------------------------- figures
def fig_architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.set_xlim(0, 110)
    ax.set_ylim(0, 56)
    ax.axis("off")

    def box(x, y, w, h, title, body, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6", fc=color, ec="#1e293b", lw=1.2))
        ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="top", fontsize=9.5, weight="bold")
        ax.text(x + w / 2, y + h - 6.6, body, ha="center", va="top", fontsize=7.6, linespacing=1.35)

    def arrow(x1, y1, x2, y2, label=""):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, lw=1.3, color="#334155"))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.2, label, ha="center", fontsize=7, color="#334155")

    C, Q, D = "#e2e8f0", "#dbeafe", "#dcfce7"
    ax.text(2, 54, "CLASSICAL (Python)", fontsize=8, color="#475569", weight="bold")
    ax.text(58, 54, "QUANTUM (Qiskit 2.x + Aer simulator)", fontsize=8, color="#1d4ed8", weight="bold")
    box(2, 36, 24, 15, "1. Scenario & network", "Karachi landmarks (real coords)\nsynthetic bus lines + timetables\nflood-damaged segments\nevacuee groups, shelter capacity", C)
    box(30, 36, 24, 15, "2. RAPTOR router", "round-based transit search\nPareto set: arrival vs. trips\nK diverse journeys per group\n(classical, exact, fast)", C)
    box(30, 14, 24, 17, "3. QUBO builder", "x[g,r] = group g takes journey r\nmin person-minutes\n+ bus crowding  (Σ load)²/cap\n+ shelter load  (Σ load)²/cap\ns.t. Σ_r x[g,r] = 1", C)
    box(58, 14, 23, 17, "4a. Penalty QAOA", "QUBO+penalty → Ising H_C\n|+⟩ⁿ start, RX mixer\nconstraint via penalty A\nCVaR-α training (COBYLA)", Q)
    box(84, 14, 24, 17, "4b. XY-mixer QAOA", "same H_C (no penalty)\nW-state per group\nXX+YY ring mixer keeps\none-hot → always feasible", Q)
    box(84, 36, 24, 15, "5. Cluster decomposition", "36 vars > simulator limit\ncluster coupled groups →\n≤12-qubit XY-QAOA each,\nblock-coordinate descent", Q)
    box(58, 36, 23, 15, "6. Dürr–Høyer min-search", "Grover + BBHT schedule on\nRAPTOR arrival labels\ncount oracle queries\nvs N−1 comparisons", Q)
    box(2, 14, 24, 17, "7. Classical baselines", "exact brute force (K^G)\ngreedy (largest group first)\nsimulated annealing\nindependent RAPTOR", D)
    box(30, 0.5, 78, 9, "8. Evaluation & export → results.json → React + Leaflet map dashboard / .docx report",
        "objective gap · P(feasible) · P(optimal) · approximation ratio · bus load factors · shelter overflow · oracle query counts", D)
    arrow(26, 43.5, 30, 43.5, "network")
    arrow(42, 36, 42, 31.6, "journeys")
    arrow(54, 43.5, 58, 43.5, "labels")
    arrow(54, 22.5, 58, 22.5, "H_C")
    arrow(81, 22.5, 84, 22.5, "")
    arrow(96, 31, 96, 36, "sub-QUBOs")
    arrow(30, 22.5, 26, 22.5, "QUBO")
    arrow(70, 14, 70, 10, "")
    arrow(100, 14, 100, 10, "")
    arrow(14, 14, 30, 6, "")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_qaoa_quality(d: dict, path: Path) -> None:
    runs = d["small"]["qaoa"]
    labels = [f"{'XY' if r['variant'] == 'xy' else 'Penalty'}\np={r['reps']}" for r in runs]
    colors = ["#2563eb" if r["variant"] == "xy" else "#d97706" for r in runs]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))
    axs[0].bar(labels, [r["p_feasible"] for r in runs], color=colors)
    axs[0].set_title("P(feasible sample)")
    axs[0].set_ylim(0, 1.05)
    rnd = 1 / (d["small"]["K"] ** len(d["small"]["groups"]))
    axs[1].bar(labels, [100 * r["p_optimal"] for r in runs], color=colors)
    axs[1].axhline(100 * rnd, color="#dc2626", ls="--", lw=1)
    axs[1].text(-0.4, 100 * rnd * 1.15, "random feasible guess", fontsize=7, color="#dc2626")
    axs[1].set_title("P(optimal sample) %")
    axs[2].bar(labels, [r["approx_ratio"] or 0 for r in runs], color=colors)
    axs[2].set_title("Approximation ratio (feasible samples)")
    axs[2].set_ylim(0, 1.05)
    for a in axs:
        a.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_landscape(d: dict, path: Path) -> None:
    s = d["small"]
    xy = [r for r in s["qaoa"] if r["variant"] == "xy"][-1]
    fig, ax = plt.subplots(figsize=(6.5, 3))
    ax.hist(s["landscape"], bins=25, color="#cbd5e1")
    for v, lab, c in ((s["exact_energy"], "exact optimum", "#059669"), (s["methods"][0]["energy"], "no coordination", "#dc2626"),
                      (xy["expected_feasible_energy"], f"QAOA-XY p={xy['reps']} mean sample", "#2563eb")):
        ax.axvline(v, color=c, lw=2, label=lab)
    ax.set_xlabel("objective (lower is better)")
    ax.set_ylabel("# assignments")
    ax.set_title(f"All {len(s['landscape'])} feasible assignments of the 12-qubit instance", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_cluster(d: dict, path: Path) -> None:
    L = d["large"]
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    ax.plot([t["step"] for t in L["trace"]], [t["energy"] for t in L["trace"]], "o-", color="#2563eb", label="clustered XY-QAOA")
    ax.axhline(L["exact_energy"], color="#059669", ls="--", label="exact optimum")
    for m in L["methods"]:
        if m["method"].startswith("Greedy"):
            ax.axhline(m["energy"], color="#d97706", ls=":", label="greedy")
    ax.set_xlabel("cluster solve step")
    ax.set_ylabel("objective")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_grover(d: dict, path: Path) -> None:
    rows = d["grover"]
    N = [r["N"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    ax.plot(N, [r["classical_comparisons"] for r in rows], "s-", color="#dc2626", label="classical scan (N−1)")
    ax.plot(N, [r["mean_queries_to_min"] for r in rows], "o-", color="#2563eb", label="Dürr–Høyer queries until min found (mean)")
    ax.plot(N, [r["sqrtN"] for r in rows], "--", color="#94a3b8", label="√N")
    ax.set_xlabel("N candidate RAPTOR labels")
    ax.set_ylabel("oracle queries / comparisons")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------- docx helpers
def table(doc, header, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(8.5)
    return t


def para(doc, text, bold_lead=None, size=10.5):
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.size = Pt(size)
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p


def bullet(doc, text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    return p


def f(v, d=1):
    return "–" if v is None else f"{v:.{d}f}"


def methods_rows(methods):
    return [[m["method"], f(m["energy"], 0), f(m["gap_pct"], 2) + "%", f(m["metrics"]["avg_travel_min"]),
             f(100 * m["metrics"]["max_bus_load_factor"], 0) + "%", m["metrics"]["overloaded_bus_segments"],
             m["metrics"]["shelter_overflow"]] for m in methods]


# ---------------------------------------------------------------- report
def main() -> None:
    d = json.loads(RESULTS.read_text())
    FIG.mkdir(parents=True, exist_ok=True)
    fig_architecture(FIG / "architecture.png")
    fig_qaoa_quality(d, FIG / "qaoa_quality.png")
    fig_landscape(d, FIG / "landscape.png")
    fig_cluster(d, FIG / "cluster.png")
    fig_grover(d, FIG / "grover.png")
    s, L, net = d["small"], d["large"], d["network"]
    xy = [r for r in s["qaoa"] if r["variant"] == "xy"]
    pen = [r for r in s["qaoa"] if r["variant"] == "penalty"]
    nfeas = s["K"] ** len(s["groups"])
    indep, exact = s["methods"][0], next(m for m in s["methods"] if m["method"].startswith("Exact"))
    Lindep = L["methods"][0]
    Lgreedy = next(m for m in L["methods"] if m["method"] == "Greedy")
    Lcl = next(m for m in L["methods"] if m["method"].startswith("Clustered"))
    Lsa = next(m for m in L["methods"] if m["method"].startswith("Simulated"))

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    h = doc.add_heading("Quantum-Assisted Evacuation Routing", 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph("RAPTOR transit routing + QAOA congestion-aware assignment for cyclone storm-surge evacuation in Karachi")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph("Qiskit Quantum Optimization Challenge · Domain 2: Disaster Response · Repository: https://github.com/MARafey/Quantum-Routing")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(9)
    p.runs[0].font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    doc.add_heading("1. Problem statement", 1)
    para(doc, "When a cyclone storm surge threatens Karachi's coastal belt (Keamari, Clifton, DHA, Korangi, Lyari, Saddar/Tower), "
         "thousands of people must be moved inland on a bus network that is itself partly flooded. A journey planner such as "
         "RAPTOR gives each group its individually fastest route, but if every group follows its own best route the same buses "
         "and the same shelters overload, which costs time and safety. ", "Motivation. ")
    para(doc, "Disaster-management authorities and transit operators who coordinate evacuation transport and need an "
         "assignment of evacuee groups to journeys that balances travel time against bus crowding and shelter capacity.", "Intended users. ")
    para(doc, "Choose one public-transport journey for every evacuee group so that total person-minutes of travel, bus "
         "overcrowding and shelter overload are jointly minimised. These objectives compete: the fastest journeys share the same "
         "trunk lines and shelters.", "Optimisation problem. ")

    doc.add_heading("2. Formulation", 1)
    para(doc, "x[g,r] ∈ {0,1}: group g (size n_g) takes journey option r ∈ {1..K}. Options are the K most attractive "
         "Pareto-optimal journeys found by RAPTOR (diverse destination shelters, several departures).", "Decision variables. ")
    para(doc, "minimise  Σ_g Σ_r n_g·(T[g,r] + 5·transfers[g,r])·x[g,r]  +  w_c·Σ_s (Σ_{g,r∋s} n_g x[g,r])² / cap_s  +  "
         "w_h·Σ_h (Σ_{g,r→h} n_g x[g,r])² / cap_h", "Objective. ")
    para(doc, "Here s ranges over individual bus-trip segments (capacity 40–60), h over shelters (capacity 160–250), and "
         "w_c = w_h = 3. The squared loads are convex congestion costs; they create the quadratic coupling between groups, so "
         "the problem is naturally a QUBO rather than a linear problem with penalty terms added on.")
    para(doc, "Σ_r x[g,r] = 1 for every group g (each group takes exactly one journey).", "Constraint. ")
    para(doc, f"Network: {len(net['stops'])} stops, {net['num_lines']} bus lines ({net['num_routes']} directed RAPTOR routes), "
         f"{net['num_trips']} timetabled trips, {len(net['damaged'])} flood-closed segments, 6 shelters. Small instance: 4 groups "
         f"(60–90 people) × K=3 options = 12 binary variables / qubits, {nfeas} feasible assignments. City-scale instance: 12 "
         "groups in two departure waves × 3 options = 36 variables (531,441 feasible assignments).", "Test instances. ")

    doc.add_heading("3. Architecture", 1)
    doc.add_picture(str(FIG / "architecture.png"), width=Inches(6.5))
    para(doc, "RAPTOR (classical, exact and fast) turns the large transit graph into a small set of candidate journeys. The "
         "combinatorial, coupled part (who takes which journey under shared capacity) is mapped to an Ising Hamiltonian and solved "
         "with QAOA on the Qiskit Aer simulator. Everything is checked against exact brute force.", size=9.5)

    doc.add_heading("4. Quantum approach and justification", 1)
    bullet(doc, " The QUBO is converted to an Ising Hamiltonian with x_i = (1 − Z_i)/2, giving a SparsePauliOp with Z and ZZ terms "
           "(one qubit per decision variable). The cost unitary exp(−iγH_C) is exact because all terms commute.", "Mapping.")
    bullet(doc, " QAOA is the standard variational algorithm for QUBO/Ising problems on near-term devices; it works directly on "
           "our quadratic congestion objective and has a natural constraint-preserving variant.", "Why QAOA.")
    bullet(doc, " Variant A (textbook): |+⟩ⁿ, RX mixer, one-hot constraint via penalty A·(Σ_r x − 1)². Variant B "
           "(Hadfield et al. 2019, Quantum Alternating Operator Ansatz): each group's 3 qubits start in a W state and the mixer is "
           "a ring of XX+YY gates, which conserves Hamming weight. The state never leaves the feasible subspace, so the "
           "penalty and its tuning disappear.", "Two variants.")
    bullet(doc, " Angles are trained with COBYLA (3 random restarts) on exact statevector probabilities using a CVaR-α loss "
           "(α = 0.2, Barkoutsos et al. 2020); the final circuit is sampled with 4096 shots on AerSimulator.", "Training.")
    bullet(doc, " For 36 variables (2³⁶ amplitudes) we split groups into clusters of ≤4 by coupling strength and re-optimise "
           "one cluster at a time with XY-QAOA (block-coordinate descent; other clusters enter as linear terms).", "Scaling.")
    bullet(doc, " Dürr–Høyer minimum finding (Grover search with the BBHT schedule) applied to RAPTOR's final label-selection "
           "step, comparing oracle queries with classical comparisons.", "Second quantum component.")

    doc.add_heading("5. Results", 1)
    doc.add_heading("5.1 12-qubit instance: QAOA vs. exact and classical baselines", 2)
    table(doc, ["Method", "Objective", "Gap to exact", "Avg travel", "Max bus load", "Overloaded segs", "Shelter overflow"],
          methods_rows(s["methods"]))
    doc.add_paragraph()
    table(doc, ["QAOA run", "P(feasible)", "P(optimal)", "Approx. ratio", "Found opt.", "Depth", "CNOTs", "Sim time (s)"],
          [[f"{'XY-mixer' if r['variant'] == 'xy' else 'Penalty'} p={r['reps']}", f(r["p_feasible"], 3), f(100 * r["p_optimal"], 2) + "%",
            f(r["approx_ratio"], 3), "yes" if r["found_optimum"] else "no", r["circuit_depth"], r["cx_count"], f(r["seconds"])]
           for r in s["qaoa"]])
    doc.add_picture(str(FIG / "qaoa_quality.png"), width=Inches(6.5))
    doc.add_picture(str(FIG / "landscape.png"), width=Inches(5.2))
    best_xy = max(xy, key=lambda r: r["p_optimal"])
    para(doc, f"Coordination matters: the exact optimum reroutes groups away from their individually fastest RAPTOR journey, "
         f"lowering the objective by {f(indep['gap_pct'], 2)}% relative to uncoordinated routing (max bus load "
         f"{f(100 * indep['metrics']['max_bus_load_factor'], 0)}% → {f(100 * exact['metrics']['max_bus_load_factor'], 0)}%). "
         f"XY-mixer QAOA returned a feasible sample {f(100 * min(r['p_feasible'] for r in xy), 1)}% of the time at every depth, "
         f"against at most {f(100 * max(r['p_feasible'] for r in pen), 1)}% for penalty QAOA. Its best probability of sampling the "
         f"exact optimum was {f(100 * best_xy['p_optimal'], 1)}% (p={best_xy['reps']}), versus {f(100 / nfeas, 2)}% for a random "
         f"feasible guess and at most {f(100 * max(r['p_optimal'] for r in pen), 2)}% for penalty QAOA. Every QAOA run had the "
         "optimum among its 4096 samples.", "Findings. ")

    doc.add_heading("5.2 City-scale instance: clustered QAOA (36 variables)", 2)
    table(doc, ["Method", "Objective", "Gap to exact", "Avg travel", "Max bus load", "Overloaded segs", "Shelter overflow"],
          methods_rows(L["methods"]))
    doc.add_picture(str(FIG / "cluster.png"), width=Inches(5.2))
    para(doc, f"Clustered XY-QAOA (clusters {L['clusters']}) reached an objective {f(Lcl['gap_pct'], 2)}% from the exact optimum "
         f"in {len(L['trace']) - 1} cluster solves. Greedy was {f(Lgreedy['gap_pct'], 2)}% from optimal, which is worse than no "
         f"coordination at all ({f(Lindep['gap_pct'], 2)}%), and simulated annealing reached {f(Lsa['gap_pct'], 2)}%.")

    doc.add_heading("5.3 Dürr–Høyer minimum search over RAPTOR labels", 2)
    table(doc, ["N labels", "Qubits", "Classical comparisons", "Quantum queries to min (mean)", "√N", "Success"],
          [[r["N"], r["qubits"], r["classical_comparisons"], f(r["mean_queries_to_min"]), f(r["sqrtN"]),
            f(100 * r["success_rate"], 0) + "%"] for r in d["grover"]])
    doc.add_picture(str(FIG / "grover.png"), width=Inches(5.2))
    para(doc, "Queries until the true minimum is first held grow roughly like √N, while the classical scan grows like N. "
         "This is a query-count comparison, not a timing comparison (see limitations).")

    doc.add_heading("6. Limitations and honest discussion", 1)
    bullet(doc, " Every quantum result comes from classical simulation. Simulation time grows as 2ⁿ, so the quantum runs "
           f"take seconds to minutes ({f(min(r['seconds'] for r in s['qaoa']))}–{f(max(r['seconds'] for r in s['qaoa']))} s) "
           f"while brute force over {nfeas} assignments takes milliseconds. We claim no speedup.", "No speedup.")
    bullet(doc, " At 4 groups, greedy and simulated annealing also find the optimum, and SA does so on the 36-variable "
           "instance too. QAOA's contribution here is shown by solution quality and feasibility, not by beating classical "
           "solvers. Instances this small are easy classically.", "Small instances are classically easy.")
    bullet(doc, f" The XY-QAOA probability of sampling the optimum is modest ({f(100 * best_xy['p_optimal'], 1)}%) because "
           "many assignments have nearly equal objectives (see the landscape plot). Deeper circuits help only a little, and "
           "the classical optimiser cost grows with depth.", "Low P(optimal).")
    bullet(doc, f" The XY mixer needs more two-qubit gates (CNOTs {xy[-1]['cx_count']} vs {pen[-1]['cx_count']} at "
           f"p={xy[-1]['reps']}). On noisy hardware that would reduce fidelity, and we did not run a noise model.", "Circuit cost.")
    bullet(doc, " The penalty strength A was set by a heuristic (1.5× max variable influence). Penalty QAOA's feasibility "
           f"depended strongly on depth ({f(100 * min(r['p_feasible'] for r in pen), 0)}–"
           f"{f(100 * max(r['p_feasible'] for r in pen), 0)}% feasible), but even when feasible its samples were spread "
           f"across poor assignments (approximation ratio ≈{f(pen[-1]['approx_ratio'], 2)}): the large penalty dominates the "
           "energy scale and flattens the real objective.", "Penalty tuning.")
    bullet(doc, " The Dürr–Høyer figures count queries until the true minimum is first held. The algorithm itself cannot "
           "detect that moment and runs to its O(√N) budget (22.5√N + 1.4 log²N), which at these small N exceeds N. The "
           "asymptotic advantage only becomes practical at much larger N.", "Query accounting.")
    bullet(doc, " The Grover oracle is a diagonal phase gate built from labels already known classically. A real advantage "
           "would need quantum-accessible memory (QRAM) and a reversible comparator, which we did not build. The √N result "
           "is about query complexity only.", "Oracle construction.")
    bullet(doc, " The cluster decomposition is a heuristic. It is only guaranteed to be locally optimal, and it uses "
           "brute force for reporting sub-problem quality, which would not scale.", "Decomposition.")
    bullet(doc, " Landmark coordinates are real, but the bus lines, timetables, capacities, damage and group sizes are "
           "synthetic. A real deployment would use GTFS feeds and live road-damage data.", "Synthetic data.")

    doc.add_heading("7. Reproducibility", 1)
    para(doc, "cd backend && uv sync && uv run qroute-demo   (all seeds fixed; writes results.json)\n"
         "uv run pytest   ·   uv run qroute-report   ·   cd frontend && npm install && npm run dev", size=9.5)
    para(doc, f"Generated {d['generated']}; full experiment runtime {f(d['runtime_seconds'], 0)} s on a laptop CPU.", size=9.5)

    doc.add_heading("8. References and credits", 1)
    for ref in [
        "D. Delling, T. Pajor, R. F. Werneck. Round-Based Public Transit Routing. Transportation Science 49(3), 2015. (RAPTOR; implemented from the paper.)",
        "E. Farhi, J. Goldstone, S. Gutmann. A Quantum Approximate Optimization Algorithm. arXiv:1411.4028, 2014.",
        "S. Hadfield et al. From the QAOA to a Quantum Alternating Operator Ansatz. Algorithms 12(2):34, 2019. (XY mixer.)",
        "P. Kl. Barkoutsos et al. Improving Variational Quantum Optimization using CVaR. Quantum 4, 256, 2020.",
        "C. Dürr, P. Høyer. A Quantum Algorithm for Finding the Minimum. arXiv:quant-ph/9607014, 1996.",
        "M. Boyer, G. Brassard, P. Høyer, A. Tapp. Tight bounds on quantum searching. Fortschr. Phys. 46, 1998.",
        "F. Neukart et al. Traffic Flow Optimization Using a Quantum Annealer. Front. ICT 4:29, 2017. (Inspiration for route-choice QUBOs.)",
        "Qiskit, Qiskit Aer (IBM). Map tiles © OpenStreetMap contributors, © CARTO. Code written by the team; no tutorial code copied.",
    ]:
        doc.add_paragraph(ref, style="List Number").runs[0].font.size = Pt(9)

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "Quantum_Evacuation_Routing_Report.docx"
    doc.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
