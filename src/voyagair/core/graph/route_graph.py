"""NetworkX-based route graph for pathfinding and multi-stop planning."""

from __future__ import annotations

import logging
import math
from typing import Any

import networkx as nx
from geopy.distance import geodesic

from voyagair.core.graph.airports import AirportDatabase
from voyagair.core.search.models import Airport

logger = logging.getLogger(__name__)

# Approximate bounding boxes for conflict-zone avoidance.
# Each entry is (name, min_lat, max_lat, min_lon, max_lon).
CONFLICT_ZONES = {
    "middle_east": {
        "name": "Middle East Conflict Zone",
        "bounds": [(10.0, 42.0, 25.0, 65.0)],
    },
    "ukraine": {
        "name": "Ukraine Conflict Zone",
        "bounds": [(44.0, 53.0, 22.0, 41.0)],
    },
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast haversine distance in km, avoiding geopy overhead for bulk computation."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _great_circle_midpoints(
    lat1: float, lon1: float, lat2: float, lon2: float, n_samples: int = 10
) -> list[tuple[float, float]]:
    """Sample points along the great circle arc between two coordinates."""
    points = []
    for i in range(1, n_samples):
        fraction = i / n_samples
        lat = lat1 + fraction * (lat2 - lat1)
        lon = lon1 + fraction * (lon2 - lon1)
        points.append((lat, lon))
    return points


def _crosses_zone(
    lat1: float, lon1: float, lat2: float, lon2: float, bounds: list[tuple[float, float, float, float]]
) -> bool:
    """Check if a great-circle segment crosses any of the given bounding boxes."""
    midpoints = _great_circle_midpoints(lat1, lon1, lat2, lon2, n_samples=12)
    all_points = [(lat1, lon1)] + midpoints + [(lat2, lon2)]
    for lat, lon in all_points:
        for min_lat, max_lat, min_lon, max_lon in bounds:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                return True
    return False


class RouteGraph:
    """Weighted directed graph of airports and routes for pathfinding."""

    def __init__(self, airport_db: AirportDatabase) -> None:
        self.db = airport_db
        self.graph = nx.DiGraph()
        self._built = False

    def build(self, avoid_zones: list[str] | None = None) -> None:
        """Build the route graph from static airport/route data.

        Args:
            avoid_zones: List of zone keys from CONFLICT_ZONES to exclude routes through.
        """
        self.graph.clear()
        zones_to_avoid = []
        for zone_key in (avoid_zones or []):
            zone = CONFLICT_ZONES.get(zone_key)
            if zone:
                zones_to_avoid.extend(zone["bounds"])

        for iata, airport in self.db.airports.items():
            self.graph.add_node(
                iata,
                name=airport.name,
                city=airport.city,
                country=airport.country_code,
                lat=airport.latitude,
                lon=airport.longitude,
            )

        skipped = 0
        for src, dst, airline in self.db.routes:
            src_ap = self.db.get(src)
            dst_ap = self.db.get(dst)
            if not src_ap or not dst_ap:
                continue

            if zones_to_avoid and _crosses_zone(
                src_ap.latitude, src_ap.longitude,
                dst_ap.latitude, dst_ap.longitude,
                zones_to_avoid,
            ):
                skipped += 1
                continue

            dist = _haversine_km(
                src_ap.latitude, src_ap.longitude,
                dst_ap.latitude, dst_ap.longitude,
            )
            if self.graph.has_edge(src, dst):
                existing = self.graph[src][dst]
                existing.setdefault("airlines", []).append(airline)
            else:
                self.graph.add_edge(
                    src, dst,
                    distance_km=dist,
                    airlines=[airline],
                )

        self._built = True
        logger.info(
            "Built route graph: %d nodes, %d edges (%d skipped for conflict zones)",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
            skipped,
        )

    def shortest_path(
        self, origin: str, destination: str, weight: str = "distance_km"
    ) -> list[str] | None:
        """Find the shortest path (by distance) between two airports."""
        try:
            return nx.shortest_path(self.graph, origin.upper(), destination.upper(), weight=weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def all_paths(
        self, origin: str, destination: str, max_stops: int = 3, cutoff: int | None = None
    ) -> list[list[str]]:
        """Find all simple paths between two airports up to max_stops intermediate nodes."""
        try:
            paths = list(
                nx.all_simple_paths(
                    self.graph,
                    origin.upper(),
                    destination.upper(),
                    cutoff=(cutoff or max_stops + 1),
                )
            )
            return sorted(paths, key=len)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def path_distance(self, path: list[str]) -> float:
        """Calculate total distance in km for a path through the graph."""
        total = 0.0
        for i in range(len(path) - 1):
            edge = self.graph.get_edge_data(path[i], path[i + 1])
            if edge:
                total += edge.get("distance_km", 0)
        return total

    def reachable_airports(self, origin: str, max_hops: int = 1) -> list[str]:
        """Get all airports reachable from origin within max_hops."""
        try:
            lengths = nx.single_source_shortest_path_length(
                self.graph, origin.upper(), cutoff=max_hops
            )
            return [node for node, dist in lengths.items() if dist > 0]
        except nx.NodeNotFound:
            return []

    def get_distance(self, src: str, dst: str) -> float | None:
        """Get the direct route distance between two airports, or None."""
        src_ap = self.db.get(src)
        dst_ap = self.db.get(dst)
        if src_ap and dst_ap:
            return _haversine_km(
                src_ap.latitude, src_ap.longitude,
                dst_ap.latitude, dst_ap.longitude,
            )
        return None

    def has_direct_route(self, src: str, dst: str) -> bool:
        return self.graph.has_edge(src.upper(), dst.upper())

    def neighbors(self, iata: str) -> list[str]:
        try:
            return list(self.graph.successors(iata.upper()))
        except nx.NetworkXError:
            return []
