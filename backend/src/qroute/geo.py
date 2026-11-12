"""World-wide road travel times and geometry via the public OSRM demo server, with a disk cache
and a haversine fallback. Every HTTP response is cached under backend/data/osrm_cache/."""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np

OSRM = "https://router.project-osrm.org"
CACHE = Path(__file__).resolve().parents[2] / "data" / "osrm_cache"
UA = "quantum-routing-hackathon/0.1"
_last_request = [0.0]


def _get_json(url: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    wait = 1.0 - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)  # demo-server usage policy: ~1 request per second
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    finally:
        _last_request[0] = time.time()
    f.write_text(json.dumps(data), encoding="utf-8")
    return data


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _fallback_matrix(points: list[tuple[float, float]]) -> np.ndarray:
    n = len(points)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j] = haversine_m(points[i], points[j]) * 1.35 / (55 / 3.6)
    return D


def travel_matrix(points: list[tuple[float, float]]) -> tuple[np.ndarray, str]:
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in points)
    try:
        d = _get_json(f"{OSRM}/table/v1/driving/{coords}?annotations=duration")
        dur = d.get("durations")
        if d.get("code") != "Ok" or dur is None or any(x is None for row in dur for x in row):
            raise ValueError("OSRM returned null durations")
        return np.array(dur, dtype=float), "osrm"
    except Exception as e:  # network down, rate limit, unroutable point...
        print(f"[geo] OSRM table failed ({e}); using haversine fallback")
        return _fallback_matrix(points), "haversine-fallback"


def route_geometry(a: tuple[float, float], b: tuple[float, float]) -> list[list[float]]:
    url = (f"{OSRM}/route/v1/driving/{a[1]:.5f},{a[0]:.5f};{b[1]:.5f},{b[0]:.5f}"
           "?overview=simplified&geometries=geojson")
    try:
        d = _get_json(url)
        pts = d["routes"][0]["geometry"]["coordinates"]
        return [[round(lat, 5), round(lon, 5)] for lon, lat in pts]
    except Exception:
        return [[round(a[0], 5), round(a[1], 5)], [round(b[0], 5), round(b[1], 5)]]
