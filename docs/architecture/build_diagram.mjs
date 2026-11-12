// Builds docs/architecture/architecture.html (+ .png) with real technology logos (simple-icons, CC0).
import { siQiskit, siReact, siFastapi, siPython, siOpenstreetmap, siLeaflet, siNumpy, siVite, siUv, siGithub } from 'simple-icons'
import { writeFileSync, mkdirSync } from 'node:fs'
import { chromium } from 'playwright-core'

// Run from this folder after: npm i simple-icons@13.21.0 playwright-core (Chrome installed)
const OUT = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
mkdirSync(OUT, { recursive: true })
const logo = (si, size = 22, color) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-label="${si.title}"><path fill="#${color || si.hex}" d="${si.path}"/></svg>`
const ui = {
  user: '<svg viewBox="0 0 24 24" width="30" height="30"><circle cx="12" cy="8" r="4" fill="none" stroke="#151a21" stroke-width="1.8"/><path d="M4 21c1.5-4.5 4.5-6.5 8-6.5s6.5 2 8 6.5" fill="none" stroke="#151a21" stroke-width="1.8" stroke-linecap="round"/></svg>',
  truck: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M2 6h11v9H2zM13 9h4l3 3v3h-7z" fill="none" stroke="#d9480f" stroke-width="1.7" stroke-linejoin="round"/><circle cx="6" cy="17" r="1.8" fill="#d9480f"/><circle cx="16" cy="17" r="1.8" fill="#d9480f"/></svg>',
  cpu: '<svg viewBox="0 0 24 24" width="18" height="18"><rect x="6" y="6" width="12" height="12" rx="1.5" fill="none" stroke="#7c5e3c" stroke-width="1.7"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" stroke="#7c5e3c" stroke-width="1.7"/></svg>',
  par: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M4 5h16M4 10h16M4 15h16M4 20h16" stroke="#0b7a69" stroke-width="1.7" stroke-linecap="round"/></svg>',
  qubit: '<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="9" fill="none" stroke="#3451c6" stroke-width="1.7"/><ellipse cx="12" cy="12" rx="9" ry="3.2" fill="none" stroke="#3451c6" stroke-width="1.2"/><path d="M12 12l4.5-6" stroke="#3451c6" stroke-width="1.7" stroke-linecap="round"/><circle cx="16.5" cy="6" r="1.6" fill="#3451c6"/></svg>',
  rank: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M4 20V12M10 20V6M16 20v-5M22 20H2" stroke="#151a21" stroke-width="1.7" stroke-linecap="round"/></svg>',
  flask: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M9 3h6M10 3v6l-5 10a1.5 1.5 0 0 0 1.3 2h11.4a1.5 1.5 0 0 0 1.3-2l-5-10V3" fill="none" stroke="#49525f" stroke-width="1.7" stroke-linejoin="round"/></svg>',
  map: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z M9 4v14 M15 6v14" fill="none" stroke="#49525f" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  db: '<svg viewBox="0 0 24 24" width="18" height="18"><ellipse cx="12" cy="5" rx="8" ry="3" fill="none" stroke="#49525f" stroke-width="1.6"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" fill="none" stroke="#49525f" stroke-width="1.6"/></svg>',
}

const html = `<!doctype html><html><head><meta charset="utf-8"><title>Architecture: quantum-assisted relief routing</title>
<style>
*{box-sizing:border-box} body{margin:0;background:#fff;font-family:"Segoe UI",system-ui,sans-serif;color:#151a21}
.canvas{position:relative;width:1800px;height:1040px;padding:28px 36px}
h1{font-size:26px;font-weight:600;margin:0;letter-spacing:-.01em} .sub{font-size:14px;color:#49525f;margin-top:4px}
.box{position:absolute;border:1.5px solid #cfd4da;border-radius:6px;background:#fff;padding:14px 16px}
.box h2{font-size:15px;font-weight:600;margin:0 0 10px;display:flex;align-items:center;gap:8px}
.box .logos{display:flex;gap:10px;align-items:center;margin-bottom:10px}
.box .logos span{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:#49525f}
.item{font-size:13px;line-height:1.45;color:#2b313a;display:block;margin:6px 0} .item.i{display:flex;gap:8px;align-items:flex-start}
.item svg{flex:none;margin-top:1px}
.tag{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#7b8592;margin-bottom:6px}
.q{border-color:#3451c6;background:#f5f7fd} .q h2{color:#2a43a8}
.c{border-color:#c9b8a4;background:#fbf9f6}
.lane{position:absolute;border-radius:8px;border:1.5px dashed #dfe3e8}
.lane-label{position:absolute;font-size:12px;font-weight:600;color:#7b8592;letter-spacing:.06em;text-transform:uppercase;background:#fff;padding:0 6px}
.pill{display:inline-block;font-size:12px;padding:2px 7px;border-radius:3px;background:#eef1fb;color:#2a43a8;font-weight:600;margin-right:4px}
.pill.c{background:#f4efe8;color:#6b4f30} .pill.g{background:#e7f4f1;color:#0b6b5c}
.mono{font-family:Consolas,"Cascadia Mono",monospace;font-size:12px}
svg.arrows{position:absolute;inset:0;pointer-events:none}
.legend{position:absolute;left:36px;bottom:22px;font-size:12px;color:#49525f;display:flex;gap:22px;align-items:center}
.legend i{display:inline-block;width:26px;height:0;border-top:2.5px solid #151a21;margin-right:6px;vertical-align:middle}
</style></head><body><div class="canvas">
<h1>Quantum-assisted disaster relief routing: system architecture</h1>
<div class="sub">From a dispatcher's stops to a ranked comparison of brute force, parallel classical and Grover-based quantum search, on real OpenStreetMap road data</div>

<div class="lane" style="left:26px;top:96px;width:300px;height:590px"></div><div class="lane-label" style="left:40px;top:88px">1 · Interface</div>
<div class="lane" style="left:346px;top:96px;width:300px;height:590px"></div><div class="lane-label" style="left:360px;top:88px">2 · Service</div>
<div class="lane" style="left:666px;top:96px;width:1108px;height:590px"></div><div class="lane-label" style="left:680px;top:88px">3 · Optimisation core</div>
<div class="lane" style="left:26px;top:716px;width:1748px;height:262px"></div><div class="lane-label" style="left:40px;top:708px">4 · Data &amp; validation</div>

<div class="box" style="left:46px;top:120px;width:260px;height:120px">
 <h2>${ui.user} Dispatcher</h2>
 <div class="item">Chooses region (Pakistan or cross-border), hubs and sites, or presses <b>Random stops</b></div>
</div>
<div class="box" style="left:46px;top:262px;width:260px;height:404px">
 <h2>Web app</h2>
 <div class="logos"><span>${logo(siReact)} React</span><span>${logo(siVite)} Vite</span><span>${logo(siLeaflet)} Leaflet</span></div>
 <div class="item i">${ui.map}<span>Map of hubs <b>A–C</b> and sites <b>1–10</b>; click to add</span></div>
 <div class="item i">${ui.truck}<span>While running, candidate plans flicker on the map</span></div>
 <div class="item i">${ui.rank}<span>Results ranked by <b>share of plans examined</b>, with time, stops and best routes drawn on real roads</span></div>
</div>

<div class="box" style="left:366px;top:120px;width:260px;height:546px">
 <h2>REST API</h2>
 <div class="logos"><span>${logo(siFastapi)} FastAPI</span><span>${logo(siPython)} Python</span><span>${logo(siUv)} uv</span></div>
 <div class="item mono">GET  /api/regions</div>
 <div class="item mono">GET  /api/random?region=</div>
 <div class="item mono">POST /api/run</div>
 <div class="item">Validates 1–3 hubs, 2–10 sites, N ≤ 4 million plans and region bounds</div>
 <div class="item">Warm process pool of 8 workers</div>
 <div class="item">Returns per method: time, plans examined, coverage %, optimal plan, road geometry</div>
</div>

<div class="box" style="left:686px;top:120px;width:330px;height:150px">
 <h2>Plan encoder</h2>
 <div class="item">Plan = site order + split among k convoys</div>
 <div class="item"><span class="mono">N = n! · C(n+k−1, k−1)</span>&nbsp;→ index register of <b>⌈log₂ N⌉ qubits</b> (21–22 qubits for 1.8–3.6 M plans)</div>
</div>
<div class="box" style="left:686px;top:292px;width:330px;height:374px">
 <h2>Objective &amp; cost oracle</h2>
 <div class="logos"><span>${logo(siNumpy)} NumPy</span></div>
 <div class="item">Minimise <b>makespan</b>: time until the last site is reached (+0.001 × total time)</div>
 <div class="item">Vectorised evaluation of every plan from the OSRM travel-time matrix</div>
 <div class="item">Oracle marks plans cheaper than the current threshold</div>
</div>

<div class="box c" style="left:1040px;top:120px;width:340px;height:250px">
 <div class="tag">Classical reference</div>
 <h2>${ui.cpu} Brute force</h2>
 <div class="item">Evaluates all N plans: <span class="pill c">100% coverage</span></div>
 <h2 style="margin-top:14px">${ui.par} Parallel classical</h2>
 <div class="item">Same exhaustive search split across 8 processes: <span class="pill g">100% coverage</span></div>
</div>
<div class="box q" style="left:1040px;top:392px;width:340px;height:274px">
 <div class="tag">Quantum</div>
 <h2>${ui.qubit} Grover minimum search</h2>
 <div class="logos"><span>${logo(siQiskit)} Qiskit</span></div>
 <div class="item">Dürr–Høyer: Grover amplification + BBHT schedule, ~√N oracle queries</div>
 <div class="item">Warm start from a classical heuristic plan (Grover adaptive search)</div>
 <div class="item">Simulation: real Qiskit circuits ≤ 12 qubits; exact closed-form Grover statistics above (unit-tested against Qiskit)</div>
</div>

<div class="box" style="left:1404px;top:120px;width:350px;height:546px">
 <h2>${ui.rank} Comparison &amp; ranking</h2>
 <div class="item">All methods must agree on the optimal plan</div>
 <div class="item">Ranked best → worst by plans examined, then time</div>
 <div class="item"><span class="pill">quantum ≈ 0.2% of plans</span></div>
 <div class="item"><span class="pill c">brute force 100%</span><span class="pill g">parallel 100%</span></div>
 <div class="item">Best routes fetched as road geometry, one OSRM request per convoy</div>
 <div class="item i">${ui.truck}<span>Output: which hub serves which site, in what order, and when the last site gets aid</span></div>
</div>

<div class="box" style="left:46px;top:740px;width:520px;height:214px">
 <h2>${ui.map} Road data</h2>
 <div class="logos"><span>${logo(siOpenstreetmap)} OpenStreetMap</span><span>OSRM routing engine</span></div>
 <div class="item">One table request per city pool: travel-time matrix for 49 Pakistani cities and 3 cross-border regions</div>
 <div class="item i">${ui.db}<span>Responses cached on disk, so runs are reproducible offline</span></div>
</div>
<div class="box" style="left:590px;top:740px;width:560px;height:214px">
 <h2>${ui.flask} Benchmarks &amp; validation</h2>
 <div class="item"><b>TSPLIB burma14</b>: distance code reproduces the published optimum 3,323</div>
 <div class="item"><b>Warm-start benchmark</b>: 20 scenarios × 5 seeds, standard vs warm-started Grover</div>
 <div class="item"><b>Qubit study</b>: register padding, problem-size sweep, circuit depth and CNOTs</div>
 <div class="item"><b>pytest</b>: closed form vs Qiskit circuit, plan encoding, Ising mapping</div>
</div>
<div class="box" style="left:1174px;top:740px;width:580px;height:214px">
 <h2>${logo(siGithub, 18, '151a21')} Deliverables</h2>
 <div class="item">Repository with reproducible code, README and setup steps</div>
 <div class="item">Report (.docx) with this diagram, results, classical comparison and limitations</div>
 <div class="item">Narrated video: problem → quantum mapping → live demo → results</div>
 <div class="item">Earlier study in the repo: RAPTOR + QAOA (penalty vs XY mixer) evacuation assignment</div>
</div>

<svg class="arrows" viewBox="0 0 1800 1040"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#151a21"/></marker>
<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#3451c6"/></marker>
<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7b8592"/></marker></defs>
<g fill="none" stroke-width="2.2">
 <path d="M176 240 V258" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M306 400 H362" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M626 196 H682" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M851 270 V288" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M1016 196 H1036" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M1016 520 H1036" stroke="#3451c6" marker-end="url(#b)"/>
 <path d="M1380 250 H1400" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M1380 530 H1400" stroke="#3451c6" marker-end="url(#b)"/>
 <path d="M1580 666 V690 H230 V670" stroke="#151a21" marker-end="url(#a)"/>
 <path d="M480 740 V706 H760 V670" stroke="#7b8592" stroke-dasharray="6 5" marker-end="url(#g)"/>
 <path d="M1150 846 H1170" stroke="#7b8592" stroke-dasharray="6 5" marker-end="url(#g)"/>
</g>
<g font-family="Segoe UI, sans-serif" font-size="12" fill="#49525f">
 <text x="314" y="392">stops</text><text x="632" y="188">plan space</text>
 <text x="1586" y="684">ranked results + routes to the map</text>
 <text x="490" y="726">travel-time matrix</text>
</g></svg>

<div class="legend"><span><i></i>request / data flow</span><span><i style="border-color:#3451c6"></i>quantum path</span><span><i style="border-top-style:dashed;border-color:#7b8592"></i>offline data &amp; experiments</span><span>Logos: Qiskit, React, Vite, Leaflet, FastAPI, Python, uv, NumPy, OpenStreetMap, GitHub (via simple-icons, CC0)</span></div>
</div></body></html>`

writeFileSync(`${OUT}/architecture.html`, html)
const b = await chromium.launch({ channel: 'chrome' })
const p = await b.newPage({ viewport: { width: 1800, height: 1040 }, deviceScaleFactor: 2 })
await p.setContent(html, { waitUntil: 'load' })
await p.screenshot({ path: `${OUT}/architecture.png` })
await b.close()
console.log('wrote', OUT)
