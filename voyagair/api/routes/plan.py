"""Plan API endpoints for multi-stop trip optimization."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db
from voyagair.core.graph.route_graph import RouteGraph
from voyagair.core.graph.solver import RouteSolver

router = APIRouter()


class OptimizeRequest(BaseModel):
    origin: str
    destination: str
    waypoints: list[str] = Field(default_factory=list)
    avoid_zones: list[str] = Field(default_factory=list)


class SuggestRequest(BaseModel):
    airports: list[str]
    destination: str
    avoid_zones: list[str] = Field(default_factory=list)


@router.post("/optimize")
async def optimize_route(request: OptimizeRequest):
    """Find the optimal ordering of waypoints between origin and destination."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    graph = RouteGraph(db)
    graph.build(avoid_zones=request.avoid_zones or None)
    solver = RouteSolver(graph, db)

    result = solver.solve_optimal_order(
        request.origin.upper(),
        request.destination.upper(),
        [w.upper() for w in request.waypoints],
    )

    if result:
        return {
            "stops": result.stops,
            "total_distance_km": result.total_distance_km,
            "legs": result.legs,
        }
    return {"error": "No viable route found"}


@router.post("/routes")
async def find_routes(request: OptimizeRequest):
    """Find routes between origin and destination avoiding conflict zones."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    graph = RouteGraph(db)
    graph.build(avoid_zones=request.avoid_zones or None)
    solver = RouteSolver(graph, db)

    routes = solver.find_routes_avoiding_zones(
        request.origin.upper(),
        request.destination.upper(),
        request.avoid_zones,
        max_stops=3,
    )

    return {
        "routes": [
            {
                "path": path,
                "stops": len(path) - 2,
                "distance_km": graph.path_distance(path),
            }
            for path in routes
        ]
    }


@router.post("/suggest-departures")
async def suggest_departures(request: SuggestRequest):
    """Compare multiple departure airports for reaching a destination."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    graph = RouteGraph(db)
    graph.build(avoid_zones=request.avoid_zones or None)
    solver = RouteSolver(graph, db)

    suggestions = solver.suggest_departure_airports(
        [a.upper() for a in request.airports],
        request.destination.upper(),
        avoid_zones=request.avoid_zones,
    )
    return {"suggestions": suggestions}
