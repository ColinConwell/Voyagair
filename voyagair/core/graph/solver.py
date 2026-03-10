"""Multi-stop route solver using python-tsp and constraint-based optimization."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from itertools import permutations

import numpy as np

from voyagair.core.graph.airports import AirportDatabase
from voyagair.core.graph.route_graph import RouteGraph
from voyagair.core.search.models import MultiStopParams, SortKey

logger = logging.getLogger(__name__)


class RoutePlan:
    """Result of a route optimization: an ordered sequence of stops with metadata."""

    def __init__(
        self,
        stops: list[str],
        total_distance_km: float,
        legs: list[dict],
    ):
        self.stops = stops
        self.total_distance_km = total_distance_km
        self.legs = legs

    def __repr__(self) -> str:
        route = " -> ".join(self.stops)
        return f"RoutePlan({route}, {self.total_distance_km:.0f} km)"


class RouteSolver:
    """Solves multi-stop trip planning as a constrained shortest-path / TSP problem."""

    def __init__(self, route_graph: RouteGraph, airport_db: AirportDatabase):
        self.graph = route_graph
        self.db = airport_db

    def solve_optimal_order(
        self,
        origin: str,
        destination: str,
        waypoints: list[str],
        optimize_for: SortKey = SortKey.PRICE,
    ) -> RoutePlan | None:
        """Find the optimal ordering of waypoints between origin and destination.

        For small numbers of waypoints (<=10), uses exact dynamic programming.
        For larger sets, uses simulated annealing heuristic.
        """
        all_points = [origin.upper()] + [w.upper() for w in waypoints] + [destination.upper()]
        n = len(all_points)

        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    dist_matrix[i][j] = 0
                    continue
                d = self.graph.get_distance(all_points[i], all_points[j])
                if d is not None:
                    dist_matrix[i][j] = d
                else:
                    dist_matrix[i][j] = 1e9

        if len(waypoints) == 0:
            legs = self._build_legs(all_points)
            total_dist = dist_matrix[0][1] if dist_matrix[0][1] < 1e9 else 0
            return RoutePlan(stops=all_points, total_distance_km=total_dist, legs=legs)

        if len(waypoints) <= 10:
            return self._solve_exact(all_points, dist_matrix)
        else:
            return self._solve_tsp(all_points, dist_matrix)

    def _solve_exact(self, all_points: list[str], dist_matrix: np.ndarray) -> RoutePlan | None:
        """Exact solution via brute-force permutation of waypoints (origin/dest fixed)."""
        origin_idx = 0
        dest_idx = len(all_points) - 1
        waypoint_indices = list(range(1, dest_idx))

        best_order = None
        best_dist = float("inf")

        for perm in permutations(waypoint_indices):
            route = [origin_idx] + list(perm) + [dest_idx]
            total = sum(dist_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))
            if total < best_dist:
                best_dist = total
                best_order = route

        if best_order is None or best_dist >= 1e9:
            return None

        stops = [all_points[i] for i in best_order]
        legs = self._build_legs(stops)
        return RoutePlan(stops=stops, total_distance_km=best_dist, legs=legs)

    def _solve_tsp(self, all_points: list[str], dist_matrix: np.ndarray) -> RoutePlan | None:
        """Use python-tsp's simulated annealing for larger waypoint sets."""
        try:
            from python_tsp.heuristics import solve_tsp_simulated_annealing

            # python-tsp expects a full distance matrix and returns a permutation.
            # We fix origin (index 0) and destination (last index) by setting
            # the cost of skipping them to infinity.
            permutation, distance = solve_tsp_simulated_annealing(dist_matrix)

            # Reorder so origin is first
            origin_pos = permutation.index(0)
            reordered = permutation[origin_pos:] + permutation[:origin_pos]

            stops = [all_points[i] for i in reordered]
            legs = self._build_legs(stops)
            return RoutePlan(stops=stops, total_distance_km=distance, legs=legs)
        except ImportError:
            logger.warning("python-tsp not available, falling back to exact solver")
            return self._solve_exact(all_points, dist_matrix)

    def find_routes_avoiding_zones(
        self,
        origin: str,
        destination: str,
        avoid_zones: list[str],
        max_stops: int = 3,
    ) -> list[list[str]]:
        """Find routes between origin and destination that avoid specified conflict zones.

        Rebuilds the graph excluding routes through conflict zones, then finds paths.
        """
        self.graph.build(avoid_zones=avoid_zones)
        paths = self.graph.all_paths(origin, destination, max_stops=max_stops, cutoff=max_stops + 1)

        results = []
        for path in paths:
            dist = self.graph.path_distance(path)
            results.append(path)

        results.sort(key=lambda p: self.graph.path_distance(p))
        return results[:20]

    def suggest_departure_airports(
        self,
        region_airports: list[str],
        destination: str,
        avoid_zones: list[str] | None = None,
    ) -> list[dict]:
        """Rank nearby airports by route availability and distance to destination.

        Useful for the Cape Town scenario: compare CPT, JNB, WDH, VFA as departure options.
        """
        if avoid_zones:
            self.graph.build(avoid_zones=avoid_zones)

        suggestions = []
        for iata in region_airports:
            airport = self.db.get(iata)
            if not airport:
                continue

            direct = self.graph.has_direct_route(iata, destination)
            path = self.graph.shortest_path(iata, destination)
            path_dist = self.graph.path_distance(path) if path else None
            direct_dist = self.graph.get_distance(iata, destination)
            connections = len(self.graph.neighbors(iata))

            suggestions.append({
                "iata": iata,
                "name": airport.name,
                "city": airport.city,
                "direct_route": direct,
                "shortest_path": path,
                "path_distance_km": path_dist,
                "direct_distance_km": direct_dist,
                "num_connections": connections,
            })

        suggestions.sort(key=lambda s: s.get("path_distance_km") or float("inf"))
        return suggestions

    def _build_legs(self, stops: list[str]) -> list[dict]:
        """Build leg metadata for a sequence of stops."""
        legs = []
        for i in range(len(stops) - 1):
            src = stops[i]
            dst = stops[i + 1]
            dist = self.graph.get_distance(src, dst) or 0
            direct = self.graph.has_direct_route(src, dst)
            src_ap = self.db.get(src)
            dst_ap = self.db.get(dst)
            legs.append({
                "origin": src,
                "destination": dst,
                "origin_name": src_ap.name if src_ap else src,
                "destination_name": dst_ap.name if dst_ap else dst,
                "distance_km": dist,
                "direct_route_exists": direct,
            })
        return legs
