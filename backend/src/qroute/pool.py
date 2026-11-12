"""Pakistan city pool, cached OSRM duration matrix and random relief scenarios."""

from __future__ import annotations

import random
import threading

import numpy as np

from . import geo
from .regions_data import DATA as _DATA

# (name, lat, lon, region, hub)
CITIES: list[tuple[str, float, float, str, bool]] = [
    ("Karachi", 24.8607, 67.0011, "Sindh", True), ("Hyderabad", 25.3960, 68.3578, "Sindh", True),
    ("Lahore", 31.5204, 74.3587, "Punjab", True), ("Islamabad", 33.6844, 73.0479, "Punjab", True),
    ("Faisalabad", 31.4504, 73.1350, "Punjab", True), ("Multan", 30.1575, 71.5249, "Punjab", True),
    ("Peshawar", 34.0151, 71.5249, "KP", True), ("Quetta", 30.1798, 66.9750, "Balochistan", True),
    ("Dadu", 26.7319, 67.7750, "Sindh", False), ("Jacobabad", 28.2769, 68.4514, "Sindh", False),
    ("Sukkur", 27.7052, 68.8574, "Sindh", False), ("Larkana", 27.5600, 68.2264, "Sindh", False),
    ("Nawabshah", 26.2442, 68.4100, "Sindh", False), ("Thatta", 24.7461, 67.9236, "Sindh", False),
    ("Badin", 24.6560, 68.8370, "Sindh", False), ("Mirpur Khas", 25.5276, 69.0111, "Sindh", False),
    ("Khairpur", 27.5295, 68.7592, "Sindh", False), ("Umerkot", 25.3633, 69.7361, "Sindh", False),
    ("Mithi", 24.7371, 69.7974, "Sindh", False),
    ("Rajanpur", 29.1044, 70.3301, "Punjab", False), ("Dera Ghazi Khan", 30.0489, 70.6455, "Punjab", False),
    ("Muzaffargarh", 30.0736, 71.1805, "Punjab", False), ("Bahawalpur", 29.3956, 71.6836, "Punjab", False),
    ("Sargodha", 32.0836, 72.6711, "Punjab", False), ("Sialkot", 32.4945, 74.5229, "Punjab", False),
    ("Gujranwala", 32.1877, 74.1945, "Punjab", False), ("Rahim Yar Khan", 28.4202, 70.2952, "Punjab", False),
    ("Jhang", 31.2681, 72.3181, "Punjab", False), ("Mianwali", 32.5839, 71.5370, "Punjab", False),
    ("Dera Ismail Khan", 31.8314, 70.9019, "KP", False), ("Swat / Mingora", 34.7717, 72.3600, "KP", False),
    ("Chitral", 35.8518, 71.7864, "KP", False), ("Abbottabad", 34.1688, 73.2215, "KP", False),
    ("Mardan", 34.1989, 72.0231, "KP", False), ("Kohat", 33.5869, 71.4414, "KP", False),
    ("Bannu", 32.9889, 70.6056, "KP", False),
    ("Sibi", 29.5430, 67.8773, "Balochistan", False), ("Turbat", 26.0012, 63.0544, "Balochistan", False),
    ("Gwadar", 25.1216, 62.3254, "Balochistan", False), ("Khuzdar", 27.8000, 66.6100, "Balochistan", False),
    ("Zhob", 31.3410, 69.4481, "Balochistan", False), ("Loralai", 30.3705, 68.5979, "Balochistan", False),
    ("Kalat", 29.0260, 66.5900, "Balochistan", False),
    ("Dera Murad Jamali", 28.5466, 68.2231, "Balochistan", False),
    ("Muzaffarabad", 34.3700, 73.4711, "GB/AJK", False), ("Gilgit", 35.9208, 74.3080, "GB/AJK", False),
    ("Skardu", 35.2971, 75.6333, "GB/AJK", False), ("Mirpur", 33.1478, 73.7517, "GB/AJK", False),
]
NAMES = [c[0] for c in CITIES]
INDEX = {c[0]: i for i, c in enumerate(CITIES)}
CONFIGS = [(1, 10), (2, 9), (3, 8)]  # N = 3,628,800 / 3,628,800 / 1,814,400

_lock = threading.Lock()
_cache: dict = {}


PAKISTAN_BBOX = (23.5, 37.5, 60.5, 77.5)  # lat_min, lat_max, lon_min, lon_max


def _mk_regions() -> dict[str, dict]:
    regs = {"pakistan": {"id": "pakistan", "name": "Pakistan floods", "bbox": PAKISTAN_BBOX,
                         "cities": CITIES, "countries": ["Pakistan"]}}
    for rid, (name, bbox, cities) in _DATA.items():
        regs[rid] = {"id": rid, "name": name, "bbox": bbox, "cities": cities,
                     "countries": list(dict.fromkeys(c[3] for c in cities))}
    return regs


REGIONS = _mk_regions()


def region_info(rid: str) -> dict:
    r = REGIONS[rid]
    return {"id": rid, "name": r["name"],
            "bbox": {"lat_min": r["bbox"][0], "lat_max": r["bbox"][1],
                     "lon_min": r["bbox"][2], "lon_max": r["bbox"][3]},
            "countries": r["countries"], "hubs": [c[0] for c in r["cities"] if c[4]]}


def in_bbox(rid: str, lat: float, lon: float) -> bool:
    b = REGIONS[rid]["bbox"]
    return b[0] <= lat <= b[1] and b[2] <= lon <= b[3]


def _matrix_with_fallback(points: list[tuple[float, float]]) -> tuple[np.ndarray, str]:
    """One OSRM table request; null pairs fall back to haversine for that pair only."""
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in points)
    try:
        d = geo._get_json(f"{geo.OSRM}/table/v1/driving/{coords}?annotations=duration")
        dur = d.get("durations")
        if d.get("code") != "Ok" or dur is None:
            raise ValueError("OSRM table not ok")
    except Exception as e:
        print(f"[pool] OSRM table failed ({e}); haversine fallback")
        return geo._fallback_matrix(points), "haversine-fallback"
    D = np.zeros((len(points), len(points)))
    nulls = 0
    for i, row in enumerate(dur):
        for j, x in enumerate(row):
            if x is None:
                nulls += 1
                D[i, j] = geo.haversine_m(points[i], points[j]) * 1.35 / (55 / 3.6)
            else:
                D[i, j] = x
    return D, ("osrm+fallback" if nulls else "osrm")


def pool_matrix(region: str = "pakistan") -> tuple[np.ndarray, str]:
    """Full pool duration matrix (one OSRM table call, then in memory)."""
    with _lock:
        if region not in _cache:
            pts = [(c[1], c[2]) for c in REGIONS[region]["cities"]]
            _cache[region] = geo.travel_matrix(pts) if region == "pakistan" else _matrix_with_fallback(pts)
        return _cache[region]


def pool_lookup(points: list[tuple[str, float, float]], region: str = "pakistan") -> list[int] | None:
    """Pool indices if every (name, lat, lon) is a pool city at its own coordinates, else None."""
    out = []
    cities = REGIONS[region]["cities"]
    index = {c[0]: i for i, c in enumerate(cities)}
    for name, lat, lon in points:
        i = index.get(name)
        if i is None or abs(cities[i][1] - lat) > 1e-4 or abs(cities[i][2] - lon) > 1e-4:
            return None
        out.append(i)
    return out


def _pt(i: int) -> dict:
    c = CITIES[i]
    return {"name": c[0], "lat": c[1], "lon": c[2]}


def _spread_ok(idx: list[int]) -> bool:
    lats = [CITIES[i][1] for i in idx]
    lons = [CITIES[i][2] for i in idx]
    return (max(lats) - min(lats) > 4 or max(lons) - min(lons) > 4) and len({CITIES[i][3] for i in idx}) >= 3


def _random_generic(rid: str, seed: int | None) -> dict:
    """Cross-border region: >=2 sites in each of 2 countries, sites span >35% of the region extent."""
    cities = REGIONS[rid]["cities"]
    rng = random.Random(seed)
    hubs_all = [i for i, c in enumerate(cities) if c[4]]
    k, n = rng.choice([(k, n) for k, n in CONFIGS if k <= len(hubs_all)])
    hubs = rng.sample(hubs_all, k)
    others = [i for i in range(len(cities)) if i not in hubs]
    lat_span = max(c[1] for c in cities) - min(c[1] for c in cities)
    lon_span = max(c[2] for c in cities) - min(c[2] for c in cities)

    def pt(i: int) -> dict:
        return {"name": cities[i][0], "lat": cities[i][1], "lon": cities[i][2]}

    for _ in range(5000):
        sites = rng.sample(others, n)
        cnt: dict[str, int] = {}
        for i in sites:
            cnt[cities[i][3]] = cnt.get(cities[i][3], 0) + 1
        lats, lons = [cities[i][1] for i in sites], [cities[i][2] for i in sites]
        spread = max(lats) - min(lats) > 0.35 * lat_span or max(lons) - min(lons) > 0.35 * lon_span
        if spread and sum(v >= 2 for v in cnt.values()) >= 2:
            return {"region": rid, "hubs": [pt(i) for i in hubs], "sites": [pt(i) for i in sites]}
    raise RuntimeError("could not draw a spread scenario")


def random_scenario(seed: int | None = None, region: str = "pakistan") -> dict:
    if region != "pakistan":
        return _random_generic(region, seed)
    rng = random.Random(seed)
    k, n = rng.choice(CONFIGS)
    hubs_all = [i for i, c in enumerate(CITIES) if c[4]]
    while True:
        hubs: list[int] = []
        for i in rng.sample(hubs_all, len(hubs_all)):
            if len(hubs) < k and all(CITIES[i][3] != CITIES[h][3] for h in hubs):
                hubs.append(i)
        if len(hubs) == k:
            break
    others = [i for i in range(len(CITIES)) if i not in hubs]
    by_region: dict[str, list[int]] = {}
    for i in others:
        by_region.setdefault(CITIES[i][3], []).append(i)
    for _ in range(2000):
        regions = rng.sample(list(by_region), rng.randint(3, len(by_region)))
        sites: list[int] = [rng.choice(by_region[r]) for r in regions]  # stratified picks
        rest = [i for i in others if i not in sites]
        sites += rng.sample(rest, max(0, n - len(sites)))
        sites = sites[:n]
        if len(set(sites)) == n and _spread_ok(sites):
            rng.shuffle(sites)
            return {"region": "pakistan", "hubs": [_pt(i) for i in hubs], "sites": [_pt(i) for i in sites]}
    raise RuntimeError("could not draw a spread scenario")
