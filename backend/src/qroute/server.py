"""HTTP API for the convoy router.  Run:  uv run qroute-server   (http://127.0.0.1:8000)"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .network import FLOOD_ZONE, LANDMARKS, SHELTERS
from .roadgraph import BBOX
from .solvers import Solver

MAX_STOPS = 7  # 6! = 720 visit orders -> 10-qubit index register

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["solver"] = Solver()
    yield
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


def main() -> None:
    import uvicorn

    uvicorn.run("qroute.server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
