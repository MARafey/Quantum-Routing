"""HTTP API for the convoy router.  Run:  uv run qroute-server   (http://127.0.0.1:8000)"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .network import FLOOD_ZONE, LANDMARKS, SHELTERS
from .roadgraph import BBOX
from . import cases as _cases
from . import vrp
from .solvers import Solver

MAX_STOPS = 7  # 6! = 720 visit orders -> 10-qubit index register

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["solver"] = Solver()
    state["pool"] = vrp.make_pool()
    yield
    state["pool"].shutdown()
    state["solver"].close()


app = FastAPI(title="Quantum convoy router", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


class Stop(BaseModel):
    lat: float = Field(ge=BBOX[0], le=BBOX[2])
    lon: float = Field(ge=BBOX[1], le=BBOX[3])


class SolveRequest(BaseModel):
    stops: list[Stop] = Field(min_length=2, max_length=MAX_STOPS)
    return_to_start: bool = False


@app.get("/api/info")
def info() -> dict:
    s = state["solver"]
    places = [{"name": k, "lat": v[0], "lon": v[1],
               "kind": "shelter" if k in SHELTERS else "flood" if k in FLOOD_ZONE else "place"}
              for k, v in LANDMARKS.items()]
    return {"bbox": BBOX, "nodes": s.g.n, "edges": s.g.num_edges, "workers": s.workers,
            "max_stops": MAX_STOPS, "places": places}


@app.post("/api/solve")
async def solve(req: SolveRequest) -> dict:
    s = state["solver"]
    try:
        return await run_in_threadpool(s.solve, [(p.lat, p.lon) for p in req.stops], req.return_to_start)
    except KeyError as e:  # a stop unreachable in the road graph
        raise HTTPException(422, f"Stop not reachable on the road network: {e}") from e


CASES_DIR = _cases.OUT_DIRS[0]


@app.get("/api/cases")
def list_cases() -> list:
    f = CASES_DIR / "index.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    f = CASES_DIR / f"{Path(case_id).name}.json"
    if not f.exists():
        raise HTTPException(404, "case not found")
    return json.loads(f.read_text(encoding="utf-8"))


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: str = "point"


class GeoRequest(BaseModel):
    depots: list[GeoPoint] = Field(min_length=1, max_length=3)
    sites: list[GeoPoint] = Field(min_length=2, max_length=9)
    return_to_depot: bool = False


@app.post("/api/solve-geo")
async def solve_geo(req: GeoRequest) -> dict:
    k, n = len(req.depots), len(req.sites)
    if vrp.num_plans(n, k) > 4_000_000:
        raise HTTPException(422, "too many plans (N must be <= 4,000,000)")
    case = {"id": "custom", "title": "Custom problem", "region": "custom", "disaster": "custom",
            "story": "User-defined depots and sites.", "return_to_depot": req.return_to_depot,
            "depots": [(d.name, d.lat, d.lon) for d in req.depots],
            "sites": [(s.name, s.lat, s.lon) for s in req.sites]}
    return await run_in_threadpool(_cases.run_case, case, state["pool"], "used", False, lambda *_: None)


def main() -> None:
    import uvicorn

    uvicorn.run("qroute.server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
