"""Synthetic disaster-scenario transit network laid over real Karachi coordinates.

Scenario: a cyclone storm surge floods the coastal belt of Karachi. Evacuee
groups gather at coastal stops and must reach inland shelters using the
(partially damaged) bus network. Landmark coordinates are approximate real
locations; the bus lines, timetables and capacities are synthetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Approximate real coordinates (lat, lon) of Karachi neighbourhoods.
LANDMARKS: dict[str, tuple[float, float]] = {
    "Keamari": (24.8170, 66.9780),
    "Lyari": (24.8650, 66.9950),
    "Tower": (24.8480, 67.0010),
    "Saddar": (24.8560, 67.0280),
    "Clifton": (24.8130, 67.0300),
    "DHA": (24.8000, 67.0650),
    "Korangi": (24.8300, 67.1300),
    "Landhi": (24.8480, 67.2050),
    "Karsaz": (24.8780, 67.0900),
    "Shah Faisal": (24.8800, 67.1500),
    "Malir": (24.8950, 67.2000),
    "Nazimabad": (24.9100, 67.0300),
    "Gulshan": (24.9200, 67.0950),
    "Jauhar": (24.9100, 67.1300),
    "North Nazimabad": (24.9420, 67.0400),
    "Orangi": (24.9500, 66.9900),
    "Sohrab Goth": (24.9550, 67.0900),
}

FLOOD_ZONE = ["Keamari", "Clifton", "DHA", "Korangi", "Lyari", "Tower"]
SHELTERS = ["Gulshan", "North Nazimabad", "Malir", "Sohrab Goth", "Jauhar", "Orangi"]

# Bus lines as landmark sequences (each line runs in both directions).
LINES: dict[str, list[str]] = {
    "R1 Coastal": ["Keamari", "Tower", "Saddar", "Clifton", "DHA", "Korangi", "Landhi"],
    "R2 Northern": ["Lyari", "Nazimabad", "North Nazimabad", "Sohrab Goth"],
    "R3 Shahrah-e-Faisal": ["Saddar", "Karsaz", "Shah Faisal", "Malir"],
    "R4 University": ["Tower", "Nazimabad", "Gulshan", "Jauhar"],
    "R5 Korangi Link": ["Korangi", "Shah Faisal", "Jauhar", "Gulshan", "Sohrab Goth"],
    "R6 Orangi": ["Keamari", "Lyari", "Orangi", "North Nazimabad"],
    "R7 DHA Express": ["DHA", "Karsaz", "Gulshan"],
    "R8 Landhi-Malir": ["Landhi", "Malir", "Jauhar"],
}

# Flood damage: (line, from_landmark, to_landmark) segments closed in both directions.
DAMAGED_SEGMENTS = [
    ("R1 Coastal", "Clifton", "DHA"),
    ("R7 DHA Express", "DHA", "Karsaz"),
]

BUS_SPEED_KMH = 22.0
HEADWAY_MIN = 8
SERVICE_SPAN_MIN = 150
STOPS_BETWEEN_LANDMARKS = 2  # interpolated intermediate stops per segment
WALK_RADIUS_M = 350
WALK_SPEED_MPM = 70.0  # metres per minute
TRANSFER_BUFFER_MIN = 2


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6_371_000.0
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


@dataclass
class Stop:
    id: int
    name: str
    lat: float
    lon: float
    landmark: bool


@dataclass
class Route:
    """A RAPTOR route: an ordered stop sequence served by trips with identical stop patterns."""

    id: int
    name: str
    stops: list[int]
    trips: list[list[int]]  # trips[t][i] = arrival(=departure) minute at stops[i]
    capacity: list[int]  # capacity per trip


@dataclass
class Network:
    stops: list[Stop]
    routes: list[Route]
    footpaths: dict[int, list[tuple[int, int]]]  # stop -> [(other_stop, walk_minutes)]
    damaged: list[list[tuple[float, float]]] = field(default_factory=list)  # polylines for display

    def stop_by_name(self, name: str) -> int:
        for s in self.stops:
            if s.name == name:
                return s.id
        raise KeyError(name)

    def num_trips(self) -> int:
        return sum(len(r.trips) for r in self.routes)


def build_network(seed: int = 7) -> Network:
    """Build the deterministic synthetic network. ``seed`` controls capacity variation."""
    import random

    rng = random.Random(seed)
    stops: list[Stop] = []
    landmark_id: dict[str, int] = {}
    for name, (lat, lon) in LANDMARKS.items():
        landmark_id[name] = len(stops)
        stops.append(Stop(len(stops), name, lat, lon, True))

    damaged = {(l, a, b) for l, a, b in DAMAGED_SEGMENTS} | {(l, b, a) for l, a, b in DAMAGED_SEGMENTS}
    damaged_polys: list[list[tuple[float, float]]] = []

    # Expand each line into stop sequences, splitting at damaged segments.
    routes: list[Route] = []
    for line_name, seq in LINES.items():
        pieces: list[list[int]] = [[landmark_id[seq[0]]]]
        for a, b in zip(seq, seq[1:]):
            pa, pb = LANDMARKS[a], LANDMARKS[b]
            inter = []
            for k in range(1, STOPS_BETWEEN_LANDMARKS + 1):
                f = k / (STOPS_BETWEEN_LANDMARKS + 1)
                lat = pa[0] + f * (pb[0] - pa[0])
                lon = pa[1] + f * (pb[1] - pa[1])
                sid = len(stops)
                stops.append(Stop(sid, f"{line_name.split()[0]} {a}-{b} {k}", lat, lon, False))
                inter.append(sid)
            if (line_name, a, b) in damaged:
                damaged_polys.append([pa] + [(stops[s].lat, stops[s].lon) for s in inter] + [pb])
                pieces.append([landmark_id[b]])  # service broken: start a new piece
            else:
                pieces[-1].extend(inter + [landmark_id[b]])
        for piece in pieces:
            if len(piece) < 2:
                continue
            for direction, pattern in (("→", piece), ("←", piece[::-1])):
                routes.append(_make_route(len(routes), f"{line_name} {direction}", pattern, stops, rng))

    footpaths: dict[int, list[tuple[int, int]]] = {s.id: [] for s in stops}
    for s in stops:
        for t in stops:
            if s.id < t.id:
                d = haversine_m((s.lat, s.lon), (t.lat, t.lon))
                if d <= WALK_RADIUS_M:
                    w = max(1, math.ceil(d / WALK_SPEED_MPM))
                    footpaths[s.id].append((t.id, w))
                    footpaths[t.id].append((s.id, w))
    return Network(stops, routes, footpaths, damaged_polys)


def _make_route(rid: int, name: str, pattern: list[int], stops: list[Stop], rng) -> Route:
    seg_min = []
    for a, b in zip(pattern, pattern[1:]):
        d_km = haversine_m((stops[a].lat, stops[a].lon), (stops[b].lat, stops[b].lon)) / 1000
        seg_min.append(max(1, round(d_km / BUS_SPEED_KMH * 60)))
    offset = rng.randrange(HEADWAY_MIN)
    trips, caps = [], []
    for start in range(offset, SERVICE_SPAN_MIN, HEADWAY_MIN):
        times = [start]
        for m in seg_min:
            times.append(times[-1] + m)
        trips.append(times)
        caps.append(rng.choice([40, 50, 60]))
    return Route(rid, name, pattern, trips, caps)
