"""Real Karachi road network from OpenStreetMap, plus the shortest-path searches the solvers use.

Data: major roads (motorway..tertiary) inside the Karachi bounding box, fetched once from
the Overpass API and cached in ``backend/data/karachi_roads.json``.
© OpenStreetMap contributors, available under the ODbL.
"""

from __future__ import annotations

import heapq
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "osm_raw.json"
CACHE = DATA / "karachi_roads.json"
BBOX = (24.78, 66.95, 24.98, 67.23)  # south, west, north, east
SPEED_KMH = {"motorway": 70, "trunk": 60, "primary": 45, "secondary": 35, "tertiary": 30}
QUERY = ('[out:json][timeout:120];way["highway"~"^(motorway|trunk|primary|secondary|tertiary|motorway_link|'
         'trunk_link|primary_link|secondary_link|tertiary_link)$"]({},{},{},{});(._;>;);out body;')


def fetch_osm() -> None:
    body = urllib.parse.urlencode({"data": QUERY.format(*BBOX)}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", body,
                                 headers={"User-Agent": "quantum-routing-hackathon/0.1"})
    RAW.write_bytes(urllib.request.urlopen(req, timeout=180).read())


def _hav(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12_742_000.0 * math.asin(math.sqrt(h))


def build_cache() -> None:
    """Raw Overpass JSON -> compact graph (largest connected component, travel-time weights)."""
    if not RAW.exists():
        fetch_osm()
    els = json.loads(RAW.read_text(encoding="utf-8"))["elements"]
    coord = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node"}
    adj: dict[int, dict[int, float]] = {}
    for w in (e for e in els if e["type"] == "way"):
        kind = w["tags"]["highway"].replace("_link", "")
        mps = SPEED_KMH.get(kind, 30) / 3.6
        nd = [n for n in w["nodes"] if n in coord]
        for a, b in zip(nd, nd[1:]):
            t = _hav(coord[a], coord[b]) / mps
            adj.setdefault(a, {})[b] = min(t, adj.get(a, {}).get(b, math.inf))
            adj.setdefault(b, {})[a] = min(t, adj.get(b, {}).get(a, math.inf))
    # Largest connected component
    seen, best = set(), []
    for s in adj:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(comp) > len(best):
            best = comp
    idx = {osm: i for i, osm in enumerate(best)}
    nodes = [[round(coord[o][0], 6), round(coord[o][1], 6)] for o in best]
    edges = [[idx[a], idx[b], round(t, 2)] for a in best for b, t in adj[a].items() if idx.get(b, -1) > idx[a]]
    CACHE.write_text(json.dumps({"attribution": "© OpenStreetMap contributors (ODbL)", "bbox": BBOX,
                                 "nodes": nodes, "edges": edges}))


class RoadGraph:
    def __init__(self) -> None:
        if not CACHE.exists():
            build_cache()
        d = json.loads(CACHE.read_text())
        self.coords = np.array(d["nodes"])
        n = len(self.coords)
        self.adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        for a, b, t in d["edges"]:
            self.adj[a].append((b, t))
            self.adj[b].append((a, t))
        self.n = n
        self.num_edges = len(d["edges"])

    def nearest(self, lat: float, lon: float) -> int:
        dl = (self.coords[:, 0] - lat) ** 2 + ((self.coords[:, 1] - lon) * math.cos(math.radians(lat))) ** 2
        return int(np.argmin(dl))

    def dijkstra(self, src: int, targets: set[int] | None = None) -> dict:
        """Dijkstra from ``src``. With ``targets`` it stops once all are settled (bounded search);
        without, it explores the whole graph (exhaustive). Returns distances, parents, settle order."""
        dist = {src: 0.0}
        parent = {src: -1}
        done: set[int] = set()
        order: list[int] = []
        remaining = set(targets) if targets else None
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u in done:
                continue
            done.add(u)
            order.append(u)
            if remaining is not None:
                remaining.discard(u)
                if not remaining:
                    break
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    parent[v] = u
                    heapq.heappush(pq, (nd, v))
        return {"dist": dist, "parent": parent, "order": order}

    @staticmethod
    def path(parent: dict, target: int) -> list[int]:
        out = []
        while target != -1:
            out.append(target)
            target = parent[target]
        return out[::-1]


if __name__ == "__main__":
    build_cache()
    g = RoadGraph()
    print(g.n, "nodes", g.num_edges, "edges")
