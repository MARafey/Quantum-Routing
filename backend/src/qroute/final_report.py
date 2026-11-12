"""Builds the final submission report (.docx) from the result JSON files and figures.

Usage:  uv run qroute-report            -> report/Quantum_Relief_Routing_Report.docx
Then convert to PDF with report/to_pdf.ps1 (Microsoft Word) — the PDF is identical to the .docx.
Every number in the tables is read from backend/results/*.json, never typed by hand.
"""

from __future__ import annotations

import math
import time

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from . import report_figs as F

OUT = F.ROOT / "report" / "Quantum_Relief_Routing_Report.docx"
MEDIA = F.ROOT / "docs" / "media"
REPO = "https://github.com/MARafey/Quantum-Routing"
REG = {"pakistan": "Pakistan floods", "turkiye-syria": "Türkiye–Syria earthquake",
       "bengal-floods": "Bengal floods (Bangladesh + India)", "nepal-himalaya": "Nepal–India Himalaya earthquake"}
INK = RGBColor(0x15, 0x1A, 0x21)
counter = {"fig": 0, "tab": 0}


# ------------------------------------------------------------------ docx helpers
def shade(cell, hex_fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def light_borders(table, color="C9CED4") -> None:
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def para(doc, text="", bold_lead=None, size=10.5, italic=False, after=6, align=None, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if align:
        p.alignment = align
    if bold_lead:
        r = p.add_run(bold_lead); r.bold = True; r.font.size = Pt(size)
        if color: r.font.color.rgb = color
    r = p.add_run(text); r.font.size = Pt(size); r.italic = italic
    if color: r.font.color.rgb = color
    return p


def bullets(doc, items, size=10.5):
    for it in items:
        lead, _, rest = it.partition("||")
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        if rest:
            r = p.add_run(lead); r.bold = True; r.font.size = Pt(size)
            r = p.add_run(rest); r.font.size = Pt(size)
        else:
            r = p.add_run(lead); r.font.size = Pt(size)


def caption(doc, kind: str, text: str) -> None:
    counter[kind] += 1
    label = "Figure" if kind == "fig" else "Table"
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(f"{label} {counter[kind]}. "); r.bold = True; r.font.size = Pt(9)
    r = p.add_run(text); r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x49, 0x52, 0x5F)


def figure(doc, path, width, text):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2); p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    caption(doc, "fig", text)


def table(doc, header, rows, text, size=8.5, widths=None, first_left=True):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"; light_borders(t)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size)
        shade(c, "EEF1F5")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            pr = cells[i].paragraphs[0]
            r = pr.add_run(str(v)); r.font.size = Pt(size)
            if i > 0 or not first_left:
                pr.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    for row in t.rows:
        for c in row.cells:
            for pr in c.paragraphs:
                pr.paragraph_format.space_after = Pt(1)
                pr.paragraph_format.keep_with_next = True   # keep the whole table (and its caption) on one page
    cap = doc.add_paragraph(); cap.paragraph_format.space_before = Pt(3)
    counter["tab"] += 1
    r = cap.add_run(f"Table {counter['tab']}. "); r.bold = True; r.font.size = Pt(9)
    r = cap.add_run(text); r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x49, 0x52, 0x5F)
    cap.paragraph_format.space_after = Pt(10)


def add_page_numbers(section) -> None:
    p = section.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(); run.font.size = Pt(9)
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt
        run._r.append(el)


def sci(x: float) -> str:
    if x < 1e6:
        return f"{x:,.0f}"
    e = int(math.floor(math.log10(x)))
    return f"{x / 10**e:.1f}×10^{e}"


# ------------------------------------------------------------------ report
def main() -> None:
    F.build_all()
    runs = F.load("region_runs.json")["rows"]
    ws = F.load("quantum_warmstart_benchmark.json")["summary"]
    tsp = F.load("tsplib_benchmark.json")
    qs = F.load("qubit_study.json")
    qaoa = F.load("results.json")
    c = F.grover_constant()
    cross = {k: F.crossover(k, c) for k in (1, 2, 3)}
    from . import report as _qaoa_study   # earlier study's figure code
    _qaoa_study.fig_qaoa_quality(qaoa, F.FIG / "qaoa_quality.png")

    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.9); sec.top_margin = Inches(0.8); sec.bottom_margin = Inches(0.8)
    add_page_numbers(sec)

    # ---- title
    h = doc.add_heading("Quantum-Assisted Disaster Relief Routing", 0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, "Grover-based minimum search over multi-convoy relief plans on real road networks", size=13, align=WD_ALIGN_PARAGRAPH.CENTER, after=2, color=RGBColor(0x49, 0x52, 0x5F))
    para(doc, f"Qiskit Quantum Optimization Challenge · Domain 2: Disaster Response · Repository: {REPO}", size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, after=2, color=RGBColor(0x49, 0x52, 0x5F))
    para(doc, f"Generated {time.strftime('%Y-%m-%d')} from the committed result files", size=9, align=WD_ALIGN_PARAGRAPH.CENTER, after=10, color=RGBColor(0x7B, 0x85, 0x92))

    q_cov = [r["methods"]["quantum"]["coverage_pct"] for r in runs]
    w_cov = [r["methods"]["quantum_ws"]["coverage_pct"] for r in runs]
    dp_ms = [r["subset_dp"]["ms"] for r in runs]
    Nmin, Nmax = min(r["N"] for r in runs), max(r["N"] for r in runs)

    # ---- 1 summary
    doc.add_heading("1. Summary", 1)
    bullets(doc, [
        f"Problem.|| Relief convoys leave a few logistics hubs and must reach many stricken towns. Which hub serves which town, and in what order, decides how long the last town waits for aid. With 8 to 10 towns and 1 to 3 hubs there are {Nmin:,} to {Nmax:,} possible plans.",
        f"Quantum approach.|| Every plan gets an index. The index lives in a register of ⌈log₂N⌉ = {min(r['qubits'] for r in runs)}–{max(r['qubits'] for r in runs)} qubits, and Dürr–Høyer minimum finding (Grover search with the BBHT schedule), implemented with Qiskit, looks for the plan with the smallest makespan, optionally warm-started by a classical heuristic. Travel times come from real OpenStreetMap roads through OSRM, in four regions covering six countries.",
        f"Result against exhaustive search.|| In all four region runs the quantum search holds the optimal plan after examining {min(q_cov):.2f}–{max(q_cov):.2f}% of the plans, about {100 / max(q_cov):,.0f}–{100 / min(q_cov):,.0f}× fewer than brute force or its 8-process parallel version, which both examine 100%. Across a fit to 13 measured instances, queries grow as {c:.2f}·√N.",
        f"Honest limits.|| The quantum stage is simulated on a laptop, so its wall-clock time is not a hardware result. A stronger classical method, exact subset dynamic programming, solves every one of these instances in {min(dp_ms):.0f}–{max(dp_ms):.0f} ms and needs fewer steps than plain Grover search beyond about {cross[2]} sites. We therefore claim a quadratic reduction in oracle queries over unstructured search, not a practical advantage.",
        "Qubits.|| The minimal register ⌈log₂N⌉ is optimal: every extra qubit pads the search space with unmarked states and multiplies the queries by about 1.4 (Section 7.5).",
    ])

    # ---- 2 problem
    doc.add_heading("2. Problem statement and motivation", 1)
    para(doc, "In the 2022 monsoon floods roughly a third of Pakistan was under water and more than 30 million people were affected. After the February 2023 earthquake, relief had to reach towns on both sides of the Türkiye–Syria border. In both disasters the same planning question arises: relief stocks sit in a handful of hubs, the stricken towns are spread over hundreds of kilometres, and every convoy-hour counts for the town served last.", "Motivation. ")
    para(doc, "National and regional disaster-management authorities and relief logistics coordinators, who must decide convoy dispatch plans quickly and re-plan as damage reports arrive.", "Intended users. ")
    para(doc, "Choose, for every stricken town (site), which convoy (hub) serves it and in what order, so that the time until the last site is reached is minimal.", "Optimisation problem. ")
    bullets(doc, [
        "Measurable objective.|| Makespan: the time at which the last site is reached, i.e. the maximum over convoys of route travel time. A tiny tie-break (0.001 × total travel time) prefers shorter total driving.",
        "Constraints.|| Every site is visited exactly once, by exactly one convoy; each convoy starts at its own hub; 1–3 hubs and 2–10 sites in the demonstrator.",
        "Competing objectives.|| Serving far towns first lowers their wait but delays the near ones; adding hubs shortens routes but splits the plan space further. Both appear in the instances below.",
    ])

    # ---- 3 formulation
    doc.add_heading("3. Formulation and test instances", 1)
    para(doc, "A plan assigns each of n sites to one of k convoys and fixes the visiting order inside each convoy. Writing the sites in one sequence and cutting it into k consecutive parts gives every plan exactly once, so the number of plans is", "Decision variables. ")
    para(doc, "N = n! · C(n+k−1, k−1)", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)
    para(doc, "Each plan is encoded as one integer index in [0, N): the rank of the site permutation times the number of compositions plus the rank of the split. The mapping is a bijection (unit-tested by round trip), so one index is one plan.", after=8)
    para(doc, "minimise  max over convoys v of T_v(plan)  +  0.001 · Σ_v T_v(plan), where T_v is the travel time of convoy v along its route from its hub, using the OSRM driving-time matrix between all points.", "Objective. ")
    rows = [[REG[r["region"]], f"{r['k']} × {r['n']}", f"{r['N']:,}", r["qubits"], f"{r['best_makespan_h']:.1f}"] for r in runs]
    table(doc, ["Region (seeded random scenario)", "Hubs × sites", "Plans N", "Qubits ⌈log₂N⌉", "Last site reached (h)"], rows,
          "Test instances. Each is a reproducible random scenario (fixed seed) drawn from a pool of real cities; sites are spread over at least two provinces or countries.", widths=[2.6, 1.0, 1.1, 1.2, 1.3])

    # ---- 4 architecture (landscape page)
    ls = doc.add_section(WD_SECTION.NEW_PAGE)
    ls.orientation = WD_ORIENT.LANDSCAPE
    ls.page_width, ls.page_height = ls.page_height, ls.page_width
    ls.left_margin = ls.right_margin = Inches(0.6); ls.top_margin = Inches(0.6); ls.bottom_margin = Inches(0.6)
    doc.add_heading("4. Architecture", 1)
    figure(doc, F.ROOT / "docs" / "architecture" / "architecture.png", 9.8,
           "System architecture: interface, REST service, optimisation core (classical references and the quantum search), and data and validation. Logos: Qiskit, React, Vite, Leaflet, FastAPI, Python, uv, NumPy, OpenStreetMap, GitHub (simple-icons, CC0).")
    ps = doc.add_section(WD_SECTION.NEW_PAGE)
    ps.orientation = WD_ORIENT.PORTRAIT
    ps.page_width, ps.page_height = ps.page_height, ps.page_width
    ps.left_margin = ps.right_margin = Inches(0.9); ps.top_margin = Inches(0.8); ps.bottom_margin = Inches(0.8)
    para(doc, "The dispatcher chooses a region and the hubs and sites (or presses Random stops). The web app sends them to a FastAPI service, which validates the request and slices the cached OSRM travel-time matrix. The optimisation core evaluates every plan classically (brute force, then the same search split over 8 processes, then exact subset DP as a stronger reference) and runs the quantum search over the plan index. The ranking compares how much of the plan space each method examined, and the best routes are fetched as real road geometry and drawn on the map.")

    # ---- 5 quantum approach
    doc.add_heading("5. Quantum approach and justification", 1)
    doc.add_heading("5.1 Representation", 2)
    para(doc, f"The N plans are indexed by a register of q = ⌈log₂N⌉ qubits (21 for 1.8 million plans, 22 for 3.6 million). Basis state |i⟩ stands for plan i; indices ≥ N are never marked. The cost of plan i is a classical function C(i), so the objective can be any function and needs no quadratic form.")
    doc.add_heading("5.2 Algorithm: Dürr–Høyer minimum finding", 2)
    bullets(doc, [
        "Pick a threshold plan y (random, or the warm-start plan).",
        "Mark all plans with C(i) < C(y) in an oracle, run j Grover iterations with j drawn by the BBHT schedule (growth factor 6/5, since the number of marked plans M is unknown), and measure.",
        "If the measured plan beats y, make it the new threshold and restart the schedule; otherwise grow the schedule.",
        "Stop after the budget 22.5·√N + 1.4·log₂²N queries. Success means the optimum was held by then.",
    ])
    doc.add_heading("5.3 Why this algorithm", 2)
    bullets(doc, [
        "Compact encoding.|| The index register needs ⌈log₂N⌉ qubits. A one-hot permutation encoding needs n² per convoy: 100 qubits for 10 sites on one convoy, against 22 here (Section 7.5).",
        "Natural fit to the objective.|| The makespan is a maximum over convoys, not a quadratic form, so a QUBO needs auxiliary variables and tuned penalties. Grover search accepts an arbitrary classical cost.",
        "Provable query reduction.|| Dürr–Høyer needs O(√N) oracle queries against N for exhaustive search. QAOA, used in our earlier evacuation study where the objective is quadratic (Appendix A), has no such guarantee.",
    ])
    doc.add_heading("5.4 Warm start", 2)
    para(doc, "A cheap classical heuristic (cheapest insertion, then relocate and 2-opt) proposes a plan, which becomes the initial threshold, as in Grover adaptive search (Gilliam et al., 2021). Its evaluations are counted in the coverage figure and reported separately, so the comparison is not flattered.")
    doc.add_heading("5.5 Simulation and verification", 2)
    para(doc, "Up to 12 qubits the search runs as real Qiskit circuits on the statevector simulator. At 21–22 qubits and thousands of iterations we use the exact closed-form Grover statistics: after j iterations the probability of measuring a marked plan is sin²((2j+1)θ) with sin θ = √(M/2^q), uniform within the marked and unmarked sets. This is the circuit's exact output distribution, and a unit test checks it against Qiskit statevector simulation of the real circuit.")
    doc.add_heading("5.6 Quantum assumptions and limitations", 2)
    bullets(doc, [
        "The oracle is emulated: all N plan costs are computed classically and queries are counted. A real device needs a reversible circuit that computes the cost of a plan from its index (or QRAM with a comparator); its ancilla qubits and depth are not estimated here.",
        "Error-correction overheads may cancel a quadratic speedup on early fault-tolerant hardware (Babbush et al., 2021).",
        "The diagonal oracle stand-in used for the circuit measurements in Section 7.5 costs about 2^q CNOTs per iteration, which no real oracle would.",
    ])

    # ---- 6 implementation
    doc.add_heading("6. Implementation and reproducibility", 1)
    table(doc, ["Module", "Role"], [
        ["roadgraph, geo, pool, regions_data", "OSRM travel-time matrices and road geometry (cached), 49 Pakistani cities and 3 cross-border regions, random scenarios"],
        ["vrp, run", "Plan indexing, vectorised evaluation, brute force, parallel brute force, Dürr–Høyer search, warm start"],
        ["dp_baseline", "Exact subset dynamic-programming baseline (Held–Karp per convoy plus min–max combine)"],
        ["server", "FastAPI: /api/regions, /api/random, /api/run, /api/cases"],
        ["bench_ws, tsplib_bench, qubit_study, region_runs", "Benchmarks that produce backend/results/*.json"],
        ["raptor, model, qaoa, cluster", "Earlier evacuation study (RAPTOR transit routing and QAOA), Appendix A"],
        ["frontend/ (React, Leaflet)", "Map UI: random stops, ranked results, animated routes"],
    ], "Code organisation (backend/src/qroute and frontend/src).", widths=[2.4, 4.3], first_left=True)
    para(doc, "Setup: install uv and Node 18+, then run `uv sync` and `uv run qroute-server` in backend/, and `npm install` and `npm run dev` in frontend/. All benchmarks use fixed seeds and cached OSRM responses, so the numbers in this report can be regenerated offline; the unit tests (pytest) check the plan encoding, the Grover statistics against Qiskit, the DP baseline against enumeration, the TSPLIB distance code and the region generators.", size=10)
    t = doc.add_table(rows=1, cols=2)
    for i, (img, cap) in enumerate((("planner_ranked_pakistan.png", "Pakistan: 1 hub, 10 sites"), ("planner_ranked_turkiye.png", "Türkiye–Syria: 1 hub, 10 sites"))):
        cell = t.rows[0].cells[i]; cell.text = ""
        p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(MEDIA / img), width=Inches(3.2))
        q = cell.add_paragraph(cap); q.alignment = WD_ALIGN_PARAGRAPH.CENTER; q.runs[0].font.size = Pt(8.5)
    caption(doc, "fig", "The web app after a run. Results are ranked by share of plans examined; the best routes are drawn on real roads.")

    # ---- 7 results
    doc.add_heading("7. Results", 1)
    doc.add_heading("7.1 Four regions, six countries", 2)
    rows = []
    for r in runs:
        m = r["methods"]
        rows.append([REG[r["region"]], f"{m['brute']['ms'] / 1000:.2f}", f"{m['parallel']['ms'] / 1000:.2f}", f"{r['subset_dp']['ms'] / 1000:.3f}",
                     f"{m['quantum']['ms'] / 1000:.2f}", f"{m['quantum_ws']['ms'] / 1000:.2f}", "yes" if all(v["optimal"] for v in m.values()) and r["subset_dp"]["matches_brute_force"] else "NO"])
    table(doc, ["Region", "Brute force (s)", "Parallel (s)", "Subset DP (s)", "Quantum, simulated (s)", "Quantum + warm start, simulated (s)", "All find the optimum"], rows,
          "Wall-clock time per method on the development laptop. The quantum times are the cost of simulating the search on a CPU, not hardware time.", size=8, widths=[2.1, 0.8, 0.8, 0.8, 0.9, 1.0, 0.8])
    rows = []
    for r in runs:
        m = r["methods"]; q, w = m["quantum"], m["quantum_ws"]
        rows.append([REG[r["region"]], f"{r['N']:,}", f"{r['subset_dp']['states']:,}", f"{q['queries_to_min']:,}", f"{q['coverage_pct']:.3f}%", f"{r['N'] / q['queries_to_min']:,.0f}×",
                     f"{w['queries_to_min']:,} + {w['heuristic_evals']:,}", f"{w['coverage_pct']:.3f}%"])
    table(doc, ["Region", "Brute force and parallel: plans", "Subset DP: steps", "Quantum: queries to best plan", "Quantum coverage", "Less than exhaustive", "Warm start: queries + heuristic evals", "Warm coverage"], rows,
          "Work done by each method. Coverage is the share of all N plans examined before the best plan was held.", size=8, widths=[1.7, 0.9, 0.8, 0.8, 0.7, 0.7, 0.9, 0.7])
    figure(doc, F.FIG / "fig_coverage.png", 6.3, "Share of plans examined in the four region runs (log scale). Exact subset DP is shown for reference: it examines about 3% of the plans, ten times more than the quantum queries but far cheaper per step.")

    doc.add_heading("7.2 Scaling with problem size", 2)
    B = qs["experiment_B"]
    rows = [[r["k"], r["n"], f"{r['N']:,}", r["q"], r["backend"].replace("exact-statevector-numpy", "exact statevector").replace("grover-closed-form", "closed form"),
             f"{r['median_queries_to_min']:,.1f}", f"{r['N_over_queries_to_min']:,.1f}×", f"{100 * r['success_rate']:.0f}%"] for r in B]
    table(doc, ["Convoys k", "Sites n", "Plans N", "Qubits", "Simulation", "Median queries to optimum", "N ÷ queries", "Success"], rows,
          "Problem-size sweep on real distances (20 seeds each). The advantage over exhaustive search grows from 1.7× at N = 24 to over 600× at N = 3.6 million; at small N there is none.", size=8, widths=[0.7, 0.6, 1.0, 0.6, 1.1, 1.1, 0.9, 0.7])
    figure(doc, F.FIG / "fig_scaling.png", 6.5, f"Left: measured Grover queries against exhaustive search, with the fit {c:.2f}·√N. Right: extrapolated operation counts for two convoys; exact subset DP needs fewer steps than Grover from n = {cross[2]} sites.")

    doc.add_heading("7.3 Warm start: what it does and does not do", 2)
    rows = []
    for rg, s in ws.items():
        rows.append([REG[rg], s["standard"]["runs"], f"{s['standard']['median_queries_to_min']:,.0f}", f"{s['warm']['mean_queries_to_min']:,.0f}", f"{s['standard']['median_coverage_pct']:.3f}%",
                     f"{s['warm']['median_coverage_pct']:.4f}%", f"{s['median_ratio_coverage_std_over_warm']:.1f}×", (f"{s['median_ratio_queries_std_over_warm']:.2f}×" if s["median_ratio_queries_std_over_warm"] else "n/a (all zero)"), f"{s['heuristic_found_optimum_pct']:.0f}%"])
    table(doc, ["Region", "Runs", "Standard: median queries", "Warm: mean queries", "Standard coverage", "Warm coverage (incl. heuristic)", "Coverage gain", "Query gain when heuristic misses", "Heuristic already optimal"], rows,
          "Standard against warm-started Dürr–Høyer, paired per scenario and quantum seed (20 Pakistan scenarios × 5 seeds; 5 × 5 for each other region). Every run found the optimum.", size=7.5, widths=[1.6, 0.4, 0.7, 0.7, 0.7, 0.8, 0.6, 0.8, 0.7])
    para(doc, "The warm start lowers total coverage by roughly 12–18×, but almost all of that gain comes from the classical heuristic hitting the optimum directly in 65–100% of scenarios. When the heuristic misses, the warm-started search needs only about 1.2–1.8× fewer queries, and in some paired runs more. We therefore present the warm start as a practical hybrid, not as evidence for a deeper quantum advantage.", size=10)
    figure(doc, F.FIG / "fig_warmstart.png", 5.4, "Median share of plans examined, standard against warm-started search.")

    doc.add_heading("7.4 Validation on a published benchmark (TSPLIB burma14)", 2)
    para(doc, "To check our cost and distance code against an external reference, we implemented the TSPLIB GEO distance and ran exact Held–Karp dynamic programming on burma14 and ulysses16, reproducing the published optima 3,323 and 6,859. We then ran the quantum search on the first n cities of burma14 (closed tours, (n−1)! orders), 20 seeds per row.", size=10)
    rows = []
    for r in tsp["rows"]:
        cd, wm = r["cold"], r.get("warm")
        rows.append([r["n"], f"{r['N']:,}", f"{r['qubits']} ({r['onehot_qubits']})", f"{r['nn_gap_pct']:.1f}%", f"{cd['queries_to_min_median']:,.1f}", f"{cd['ratio_N_over_queries_median']:.1f}×" if cd["ratio_N_over_queries_median"] else "–",
                     f"{wm['queries_to_min_median']:,.1f}" if wm else "–", f"{100 * cd['success_rate']:.0f}%"])
    table(doc, ["Cities n", "Tours N", "Qubits (one-hot)", "Nearest-neighbour gap", "Cold: median queries", "N ÷ queries", "Warm: median queries", "Success"], rows,
          "burma14 prefixes. Qiskit statevector circuits for n ≤ 7 (q ≤ 10), exact closed-form statistics above. Warm start helps only at n = 5; elsewhere it is within noise.", size=8, widths=[0.6, 1.0, 1.0, 1.0, 0.9, 0.8, 0.9, 0.7])
    figure(doc, F.FIG / "fig_tsplib.png", 6.2, "Left: reduction against exhaustive enumeration on burma14 prefixes. Right: qubits needed by the index register and by a one-hot encoding for the same tours.")
    para(doc, "Published Grover-style TSP studies report 31 qubits for a 7-node TSP with 86.7% optimal-solution success (arXiv 2212.02735) and 24 and 56 qubits for 4 and 5 cities with a standard Grover encoding (ICTC 2025). The index register needs 10 qubits for 7 cities. These encodings are different trade-offs: ours pushes the work into a reversible cost oracle that we do not build.", size=10)

    doc.add_heading("7.5 Qubits: how many we used and what changes with the count", 2)
    para(doc, f"We use q = ⌈log₂N⌉ qubits: 21 for 1.8 million plans and 22 for 3.6 million. To test whether this is the right number we ran three experiments (backend/results/qubit_study.json).", size=10)
    A = qs["experiment_A"]
    inst = sorted({(r["k"], r["n"]) for r in A})
    rows = []
    for (k, n) in inst:
        rs = sorted((r for r in A if r["k"] == k and r["n"] == n), key=lambda r: r["extra"])
        rows.append([f"k={k}, n={n} (N={rs[0]['N']:,})"] + [f"{r['median_queries_to_min']:,.0f} ({r['qtm_ratio_vs_extra0']:.2f}×)" for r in rs])
    table(doc, ["Instance", "+0 qubits (minimal)", "+1", "+2", "+3", "+4"], rows,
          "Experiment A, register padding. Median queries to the optimum when the register is larger than ⌈log₂N⌉ (30 seeds). Success stayed at 100% throughout.", size=8, widths=[2.0, 1.2, 0.9, 0.9, 0.9, 0.9])
    para(doc, "Experiment A answers the question about the optimal number of qubits. Fewer than ⌈log₂N⌉ qubits cannot index all plans, and every extra qubit only adds unmarked states, so the minimal register had the lowest median queries in all three instances. Each extra qubit multiplies the queries by about 1.4 (+4 qubits gave 3.5–4.2×) without changing the success rate.", size=10)
    C_ = qs["experiment_C"]
    rows = [[r["q"], r["depth_per_iter"], r["cx_per_iter"], r["cx_oracle_standin"], r["cx_diffuser"], f"{r['statevector_bytes']:,}"] for r in C_]
    table(doc, ["Qubits q", "Depth per iteration", "CNOTs per iteration", "of which oracle stand-in", "of which diffuser", "Statevector bytes"], rows,
          "Experiment C, circuit resources of one Grover iteration in Qiskit (transpiled to cx, rz, sx, x). CNOTs grow about 1.9× per qubit, dominated by the generic diagonal oracle stand-in; the diffuser grows far more slowly. Memory doubles per qubit, which is why we switch to closed-form statistics above 12 qubits.", size=8, widths=[0.9, 1.1, 1.1, 1.2, 1.1, 1.3])
    enc = qs["encodings"]["cases"]
    rows = [[e["k"], e["n"], f"{e['N']:,}", e["index_register_qubits"], e["one_hot_tsp_n2"], e["one_hot_tsp_n_minus_1_sq"]] for e in enc]
    table(doc, ["Convoys k", "Sites n", "Plans N", "Index register (ours)", "One-hot n²", "One-hot (n−1)²"], rows,
          "Qubit counts of alternative encodings of the same problems. The index register is far smaller but excludes the ancillas of a reversible cost oracle.", size=8, widths=[0.8, 0.7, 1.1, 1.3, 1.0, 1.1])
    para(doc, "Conclusion on qubits: the optimal register is the minimal ⌈log₂N⌉; a more compact register does not exist, and larger registers cost queries. The practical limit on today's classical simulators is the statevector memory of 16·2^q bytes, which is the reason for the closed-form statistics at 21–22 qubits.", size=10)
    figure(doc, F.ROOT / "backend" / "results" / "qubit_study.png", 6.5, "Qubit study. Left: queries against padding qubits. Middle: queries and N against qubits. Right: CNOTs per Grover iteration.")

    # ---- 8 discussion
    doc.add_heading("8. When quantum search helps, and when it does not", 1)
    para(doc, "Against exhaustive search the picture is clear and grows with problem size. Against the best classical exact algorithm it is not, and the report would be incomplete without that comparison. Exact subset dynamic programming solves the min–makespan problem in about k·2ⁿ·n² + (k−1)·3ⁿ steps; using the measured Grover constant c = " + f"{c:.2f} (queries ≈ c·√N), Table {counter['tab'] + 1} compares step counts for two convoys.")
    rows = []
    for n in (8, 10, 12, 14, 16, 18, 20):
        rows.append([n, sci(F.num_plans(n, 2)), sci(F.dp_steps(n, 2)), sci(c * math.sqrt(F.num_plans(n, 2)))])
    table(doc, ["Sites n (k = 2)", "Exhaustive: N", "Subset DP: steps", "Grover: c·√N queries"], rows,
          f"Operation counts, extrapolated. Exact DP needs fewer steps than plain Grover from n = {cross[1]} sites (k = 1), {cross[2]} (k = 2) and {cross[3]} (k = 3). One Grover query would additionally need a reversible plan-cost evaluation, while a DP step is a few arithmetic operations.", size=8.5, widths=[1.5, 1.6, 1.6, 1.8])
    bullets(doc, [
        "Where it helps.|| Unstructured or black-box plan spaces where only the cost of a complete plan can be evaluated (for example a simulator-based cost with damage, time windows and capacities). There the √N query reduction over exhaustive search is real: 350–800× at 1.8–3.6 million plans, and it grows with N.",
        "Where it does not.|| When the cost decomposes (as here, with free-flow travel times) classical DP is exact, instant at these sizes (20–41 ms), and needs fewer steps than plain Grover above about 16–17 sites.",
        "Route to a real advantage.|| Hybrid algorithms that combine Grover search with a partial dynamic-programming table reach O*(1.728ⁿ) for TSP, below the O*(2ⁿ) of Held–Karp (Ambainis et al., 2019). Applying them to the multi-convoy problem is future work.",
    ])

    # ---- 9 limitations
    doc.add_heading("9. Limitations", 1)
    bullets(doc, [
        "Simulation.|| All quantum results are classical simulation. Above 12 qubits we use exact closed-form Grover statistics (verified against Qiskit at small sizes) because a 22-qubit circuit with thousands of iterations is impractical to simulate gate by gate.",
        "Emulated oracle.|| Plan costs are computed classically; no reversible cost circuit, ancilla count or fault-tolerant resource estimate is provided.",
        "Baselines.|| Brute force is a weak baseline. Exact subset DP is faster in wall-clock time and, beyond about 16–17 sites, in step count. The query reduction is real but is measured against exhaustive search.",
        "Warm start.|| Its coverage gain is mostly the classical heuristic's own accuracy (Section 7.3).",
        "Model realism.|| Travel times are free-flow OSRM estimates between city centres. Flooded or damaged roads, vehicle capacity, relief quantities and time windows are not modelled.",
        "Statistics.|| Region runs use one seeded scenario each; the qubit study uses fixed city subsets and 20–30 seeds per cell; the warm-start benchmark uses 20 Pakistan and 5 scenarios per other region.",
        "Scale of the demonstrator.|| 1–3 hubs, at most 10 sites and N ≤ 4 million, limited by the memory of the classical oracle table.",
        "External service.|| The public OSRM server is rate-limited; responses are cached in the repository so results reproduce offline.",
    ])

    # ---- appendix
    doc.add_heading("Appendix A. Earlier study: evacuation assignment with RAPTOR and QAOA", 1)
    para(doc, "Our first approach routed evacuee groups over a synthetic bus network laid on Karachi's real coordinates. RAPTOR (classical, exact) finds Pareto-optimal transit journeys for each group; a QUBO then picks one journey per group to minimise person-minutes plus bus crowding and shelter load, with exactly one journey per group. Because this objective is quadratic, QAOA is a natural fit. We compared textbook QAOA with a one-hot penalty against a constraint-preserving XY-mixer QAOA, both trained with a CVaR objective and sampled with 4096 shots on Qiskit Aer.", size=10)
    rows = [[("XY mixer" if x["variant"] == "xy" else "Penalty") + f", p={x['reps']}", f"{100 * x['p_feasible']:.0f}%", f"{100 * x['p_optimal']:.1f}%", f"{x['approx_ratio']:.2f}", "yes" if x["found_optimum"] else "no"] for x in qaoa["small"]["qaoa"]]
    table(doc, ["Variant", "Feasible samples", "Optimal samples", "Approximation ratio", "Optimum found"], rows,
          f"12-qubit instance (4 groups × 3 journeys, {3 ** 4} feasible assignments). A random feasible guess samples the optimum {100 / 81:.1f}% of the time.", size=8.5, widths=[1.6, 1.2, 1.2, 1.3, 1.1])
    gaps = {m["method"]: m["gap_pct"] for m in qaoa["large"]["methods"]}
    para(doc, f"The XY mixer keeps every sample feasible by construction. On a 36-variable instance, clustered XY-QAOA (≤12-qubit sub-problems solved in turn) reached the exact optimum (gap {gaps['Clustered XY-QAOA']:.2f}%), while greedy was {gaps['Greedy']:.2f}% above it, worse than no coordination ({gaps['Independent RAPTOR (no coordination)']:.2f}%). What did not work well: penalty QAOA needed depth to become feasible and tuned penalties, and XY p=2 sampled the optimum less often than p=1, a sign that the classical optimiser (COBYLA with three restarts) got stuck in local optima.", size=10)
    figure(doc, F.FIG / "qaoa_quality.png", 6.3, "QAOA study: feasibility, optimal-sample probability and approximation ratio, penalty against XY mixer.")

    # ---- references
    doc.add_heading("References and credits", 1)
    refs = [
        "C. Dürr, P. Høyer. A Quantum Algorithm for Finding the Minimum. arXiv:quant-ph/9607014, 1996.",
        "M. Boyer, G. Brassard, P. Høyer, A. Tapp. Tight bounds on quantum searching. Fortschr. Phys. 46, 1998.",
        "L. K. Grover. A fast quantum mechanical algorithm for database search. STOC 1996.",
        "A. Gilliam, S. Woerner, C. Gonciulea. Grover Adaptive Search for Constrained Polynomial Binary Optimization. Quantum 5, 428, 2021.",
        "R. Babbush et al. Focus beyond quadratic speedups for error-corrected quantum advantage. PRX Quantum 2, 010103, 2021.",
        "A. Ambainis et al. Quantum speedups for exponential-time dynamic programming algorithms. SODA 2019 (arXiv:1807.05209).",
        "arXiv:2212.02735 (Grover adaptive search for TSP); ICTC 2025 F01-4 (Grover TSP qubit counts); arXiv:2106.05948 and 2012.04984 (D-Wave studies on TSPLIB).",
        "M. Held, R. Karp. A dynamic programming approach to sequencing problems. 1962. G. Reinelt. TSPLIB, 1991.",
        "E. Farhi et al., 2014 (QAOA); S. Hadfield et al., 2019 (XY mixer); P. Barkoutsos et al., 2020 (CVaR); D. Delling, T. Pajor, R. Werneck, 2015 (RAPTOR).",
        "Qiskit and Qiskit Aer (IBM); FastAPI; React; Leaflet; NumPy. Road data, routing and map tiles © OpenStreetMap contributors (ODbL), routing by OSRM. Logos from simple-icons (CC0). All code was written for this project; no tutorial code was copied.",
    ]
    for r in refs:
        p = doc.add_paragraph(r, style="List Number"); p.paragraph_format.space_after = Pt(2)
        for run in p.runs:
            run.font.size = Pt(9)

    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
