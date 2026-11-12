"""RAPTOR (Round-bAsed Public Transit Optimized Router).

Implementation of the algorithm described in:
  D. Delling, T. Pajor, R. F. Werneck, "Round-Based Public Transit Routing",
  Transportation Science 49(3), 2015 (ALENEX 2012).

Written from the paper for this project. Round k computes the earliest arrival
at every stop using at most k trips, so the improving labels at a target over
rounds form the Pareto set (arrival time vs. number of trips).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from .network import TRANSFER_BUFFER_MIN, Network

INF = 10**9


@dataclass
class Leg:
    kind: str  # "bus" | "walk"
    from_stop: int
    to_stop: int
    dep: int
    arr: int
    route: int = -1
    trip: int = -1
    board_idx: int = -1
    alight_idx: int = -1


@dataclass
class Journey:
    origin: int
    target: int
    dep: int
    arr: int
    legs: list[Leg] = field(default_factory=list)

    @property
    def trips(self) -> int:
        return sum(1 for l in self.legs if l.kind == "bus")

    @property
    def transfers(self) -> int:
        return max(0, self.trips - 1)

    def segments(self) -> list[tuple[int, int, int]]:
        """Vehicle segments used: (route, trip, stop_index_from). Used for crowding."""
        out = []
        for l in self.legs:
            if l.kind == "bus":
                out.extend((l.route, l.trip, i) for i in range(l.board_idx, l.alight_idx))
        return out

    def signature(self) -> tuple:
        return tuple((l.kind, l.route, l.trip, l.from_stop, l.to_stop) for l in self.legs)


@dataclass
class RaptorResult:
    source: int
    dep: int
    arr: list[list[int]]  # arr[k][stop]
    parent: list[list[tuple | None]]
    rounds_run: int
    routes_scanned: int
    labels_improved: int


class Raptor:
    def __init__(self, net: Network):
        self.net = net
        self.routes_at_stop: dict[int, list[tuple[int, int]]] = {s.id: [] for s in net.stops}
        for r in net.routes:
            for idx, s in enumerate(r.stops):
                self.routes_at_stop[s].append((r.id, idx))
        # Per route, per stop index, the sorted departure times (trips are FIFO).
        self.dep_cols = [[[t[i] for t in r.trips] for i in range(len(r.stops))] for r in net.routes]

    def earliest_trip(self, route: int, idx: int, t: int) -> int:
        """Index of earliest trip of ``route`` departing stop index ``idx`` at or after ``t``."""
        col = self.dep_cols[route][idx]
        j = bisect.bisect_left(col, t)
        return j if j < len(col) else -1

    def run(self, source: int, dep: int, max_rounds: int = 4) -> RaptorResult:
        net = self.net
        n = len(net.stops)
        arr = [[INF] * n]
        parent: list[list[tuple | None]] = [[None] * n]
        best = [INF] * n
        arr[0][source] = dep
        best[source] = dep
        marked = {source}
        routes_scanned = labels = 0
        # Initial footpaths from the source.
        for q, w in net.footpaths[source]:
            if dep + w < best[q]:
                arr[0][q] = best[q] = dep + w
                parent[0][q] = ("walk", source, w, 0)
                marked.add(q)

        k = 0
        for k in range(1, max_rounds + 1):
            arr.append(arr[k - 1][:])
            parent.append(parent[k - 1][:])
            # Collect routes to scan, each from its earliest marked stop.
            queue: dict[int, int] = {}
            for p in marked:
                for rid, idx in self.routes_at_stop[p]:
                    if rid not in queue or idx < queue[rid]:
                        queue[rid] = idx
            marked = set()
            for rid, start in queue.items():
                routes_scanned += 1
                route = net.routes[rid]
                trip, board_stop, board_idx = -1, -1, -1
                for idx in range(start, len(route.stops)):
                    p = route.stops[idx]
                    if trip >= 0:
                        t_arr = route.trips[trip][idx]
                        if t_arr < best[p]:
                            arr[k][p] = best[p] = t_arr
                            parent[k][p] = ("trip", rid, trip, board_stop, board_idx, idx, k)
                            marked.add(p)
                            labels += 1
                    # Can we catch an earlier trip here?
                    prev = arr[k - 1][p]
                    if prev < INF:
                        buffer = 0 if (p == source and k == 1) else TRANSFER_BUFFER_MIN
                        if trip < 0 or prev + buffer <= route.trips[trip][idx]:
                            j = self.earliest_trip(rid, idx, prev + buffer)
                            if j >= 0 and (trip < 0 or j < trip):
                                trip, board_stop, board_idx = j, p, idx
            # Footpath relaxation from stops improved this round.
            for p in list(marked):
                for q, w in net.footpaths[p]:
                    if arr[k][p] + w < best[q]:
                        arr[k][q] = best[q] = arr[k][p] + w
                        parent[k][q] = ("walk", p, w, k)
                        marked.add(q)
            if not marked:
                break
        return RaptorResult(source, dep, arr, parent, k, routes_scanned, labels)

    def reconstruct(self, res: RaptorResult, target: int, k: int) -> Journey | None:
        if res.arr[k][target] >= INF:
            return None
        legs: list[Leg] = []
        stop, rnd = target, k
        guard = 0
        while stop != res.source or rnd > 0:
            guard += 1
            if guard > 50:
                return None
            entry = res.parent[rnd][stop]
            if entry is None:
                if stop == res.source:
                    break
                return None
            if entry[0] == "walk":
                _, frm, w, k_set = entry
                t_arr = res.arr[k_set][stop]
                legs.append(Leg("walk", frm, stop, t_arr - w, t_arr))
                stop, rnd = frm, k_set
            else:
                _, rid, trip, board_stop, b_idx, a_idx, k_set = entry
                route = self.net.routes[rid]
                legs.append(
                    Leg("bus", board_stop, stop, route.trips[trip][b_idx], route.trips[trip][a_idx], rid, trip, b_idx, a_idx)
                )
                stop, rnd = board_stop, k_set - 1
        legs.reverse()
        return Journey(res.source, target, res.dep, res.arr[k][target], legs)

    def pareto_journeys(self, res: RaptorResult, target: int) -> list[Journey]:
        """Pareto-optimal journeys (arrival vs. trips) to ``target``."""
        out, last = [], INF
        for k in range(1, len(res.arr)):
            a = res.arr[k][target]
            if a < last:
                j = self.reconstruct(res, target, k)
                if j is not None:
                    out.append(j)
                last = a
        return out
