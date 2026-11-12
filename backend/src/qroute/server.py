"""HTTP API for the convoy router.  Run:  uv run qroute-server   (http://127.0.0.1:8000)"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import cases as _cases
from . import pool, run, vrp

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["pool"] = vrp.make_pool()
    asyncio.get_running_loop().run_in_executor(None, pool.pool_matrix)  # warm the OSRM pool matrix
    yield
    state["pool"].shutdown()


app = FastAPI(title="Quantum convoy router", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


class Pt(BaseModel):
    name: str = "point"
    lat: float = Field(ge=23.5, le=37.5)
    lon: float = Field(ge=60.5, le=77.5)


class RunRequest(BaseModel):
    hubs: list[Pt] = Field(min_length=1, max_length=3)
    sites: list[Pt] = Field(min_length=2, max_length=10)
    return_to_depot: bool = False


@app.get("/api/random")
def random_route(seed: int | None = None) -> dict:
    return pool.random_scenario(seed)


@app.post("/api/run")
async def run_route(req: RunRequest) -> dict:
    k, n = len(req.hubs), len(req.sites)
    N = vrp.num_plans(n, k)
    if N > 4_000_000:
        raise HTTPException(422, f"Too many possible plans (N={N:,}); remove a site or a hub")
    return await run_in_threadpool(run.run_plan, [h.model_dump() for h in req.hubs],
                                   [s.model_dump() for s in req.sites], state["pool"], req.return_to_depot)


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
