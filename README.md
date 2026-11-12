# Quantum-Routing: Quantum-Assisted Evacuation Routing

**Qiskit Quantum Optimization Challenge · Domain 2: Disaster Response**

A cyclone storm surge floods Karachi's coastal belt. Evacuee groups must reach inland shelters on a partly damaged bus network. If every group takes its individually fastest route, the same buses and shelters overload. This project **coordinates** the journey choices of all groups so that travel time, bus crowding and shelter overload are jointly minimised:

1. **RAPTOR** (classical, exact) finds Pareto-optimal transit journeys for each group on the full network.
2. A **QUBO** chooses one journey per group: person-minutes + (bus load)²/capacity + (shelter load)²/capacity, with one journey per group.
3. **QAOA** on the Qiskit Aer simulator solves the QUBO in two variants: textbook *penalty* QAOA and constraint-preserving *XY-mixer* QAOA (always feasible), trained with a CVaR objective.
4. **Clustered QAOA** handles the 36-variable city-scale instance as a series of ≤12-qubit sub-problems.
5. **Dürr–Høyer** (Grover-based) minimum search is applied to RAPTOR's label selection and compared by **oracle query count**.
6. Everything is checked against **exact brute force**, **greedy** and **simulated annealing**, then visualised on a map.

> This is a simulator proof of concept. **No quantum speedup is claimed.** See the limitations section of the report.

## Repository layout

```
backend/                 Python package (uv)
  src/qroute/
    network.py           synthetic Karachi transit network (real landmark coordinates)
    raptor.py            RAPTOR router (Delling et al.), written from the paper
    model.py             evacuation model → QUBO → Ising (SparsePauliOp)
    qaoa.py              penalty & XY-mixer QAOA, CVaR training, Aer sampling
    cluster.py           cluster decomposition for large instances
    grover_min.py        Dürr–Høyer quantum minimum finding
    baselines.py         brute force, greedy, simulated annealing
    run_demo.py          runs all experiments → results.json
    report.py            builds the .docx report and figures
  tests/                 pytest: Ising == QUBO, XY mixer feasibility, RAPTOR validity
  results/               results.json + run log from the last full run
frontend/                React + Vite + Leaflet dashboard (reads public/results.json)
report/                  Quantum_Evacuation_Routing_Report.docx + figures
```

## Setup and running

Requirements: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically) and Node.js 18+.

```bash
# 1. Backend: install and run all experiments (~10 min on a laptop; --quick for ~3 min)
cd backend
uv sync
uv run qroute-demo            # writes backend/results/results.json and frontend/public/results.json
uv run pytest                 # unit tests
uv run qroute-report          # rebuilds report/Quantum_Evacuation_Routing_Report.docx

# 2. Frontend: interactive map dashboard
cd ../frontend
npm install
npm run dev                   # open the printed http://localhost:5173
```

A `results.json` from our full run is already committed, so the dashboard works without re-running the backend. All random seeds are fixed, so re-running reproduces the same numbers.

## Dashboard

- **12-qubit QAOA vs exact**: map of the four groups' chosen journeys for any method (click a table row), P(feasible) / P(optimal) per QAOA variant and depth, training curves, the full energy landscape, and the most frequently measured bitstrings.
- **City-scale (clustered)**: 12 groups in two waves, clustered XY-QAOA trace vs exact, greedy and annealing.
- **Grover min-search**: oracle queries vs classical comparisons for N = 8…64 RAPTOR labels.

## Headline results

See `backend/results/run_log.txt` and the report for the full numbers.

12-qubit instance (4 groups × 3 journeys, 81 feasible assignments, 4096 shots):

| QAOA | P(feasible) | P(optimal) | Approx. ratio |
|---|---|---|---|
| Penalty p=1 / 2 / 3 | 39% / 58% / 98% | 0.6% / 0.7% / 1.3% | 0.52 |
| **XY-mixer p=1 / 2 / 3** | **100% / 100% / 100%** | **15.1% / 6.7% / 16.8%** | 0.79–0.86 |

A random feasible guess finds the optimum 1.2% of the time. The coordinated optimum is 1.44% better than uncoordinated routing (everyone taking their fastest RAPTOR journey).

36-variable city instance: **clustered XY-QAOA reaches the exact optimum (0.00% gap)**. Greedy is 1.61% worse, and even worse than no coordination (1.03%).

Dürr–Høyer over RAPTOR labels: about 25 oracle queries to reach the minimum at N=64, against 63 classical comparisons (query count, not time).

## Credits

RAPTOR: Delling, Pajor & Werneck (2012/2015). QAOA: Farhi et al. (2014). XY mixer: Hadfield et al. (2019). CVaR: Barkoutsos et al. (2020). Minimum finding: Dürr & Høyer (1996), BBHT (1998). Route-choice QUBO idea inspired by Neukart et al. (2017). Built with Qiskit and Qiskit Aer. Map tiles © OpenStreetMap contributors / CARTO. All code was written for this project; no tutorial code was copied.
