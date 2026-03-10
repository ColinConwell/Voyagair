"""Tool definitions for the AI travel agent."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db
from voyagair.core.graph.route_graph import RouteGraph
from voyagair.core.graph.solver import RouteSolver
from voyagair.core.search.models import CabinClass, SearchParams, SortKey
from voyagair.core.search.orchestrator import SearchOrchestrator

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for flights between airports on specific dates. Returns a list of flight offers with prices, durations, and carriers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport IATA code (e.g. CPT, JNB)"},
                    "destination": {"type": "string", "description": "Destination airport IATA code (e.g. JFK, EWR)"},
                    "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "adults": {"type": "integer", "description": "Number of passengers", "default": 1},
                    "max_price": {"type": "number", "description": "Maximum price filter (optional)"},
                    "max_stops": {"type": "integer", "description": "Maximum number of stops (optional)"},
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_airport",
            "description": "Search for airports by name, city, or IATA code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (airport name, city, or IATA code)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_routes",
            "description": "Find routes between two airports, optionally avoiding conflict zones like the Middle East or Ukraine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport IATA code"},
                    "destination": {"type": "string", "description": "Destination airport IATA code"},
                    "avoid_zones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Conflict zones to avoid: 'middle_east', 'ukraine'",
                    },
                    "max_stops": {"type": "integer", "description": "Maximum intermediate stops", "default": 3},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_departure_airports",
            "description": "Compare multiple departure airports for reaching a destination, showing which has the best connections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "airports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of airport IATA codes to compare (e.g. ['CPT', 'JNB', 'WDH'])",
                    },
                    "destination": {"type": "string", "description": "Target destination IATA code"},
                    "avoid_zones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Conflict zones to avoid",
                    },
                },
                "required": ["airports", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_route",
            "description": "Find the optimal ordering of waypoints for a multi-stop trip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Start airport IATA code"},
                    "destination": {"type": "string", "description": "End airport IATA code"},
                    "waypoints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Intermediate airports to visit",
                    },
                },
                "required": ["origin", "destination", "waypoints"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool call and return the result as a JSON string."""
    config = get_config()

    if name == "search_flights":
        orchestrator = SearchOrchestrator.from_config(config)
        try:
            params = SearchParams(
                origins=[arguments["origin"].upper()],
                destinations=[arguments["destination"].upper()],
                departure_dates=[date.fromisoformat(arguments["date"])],
                adults=arguments.get("adults", 1),
                max_price=arguments.get("max_price"),
                max_stops=arguments.get("max_stops"),
                limit=10,
            )
            results = await orchestrator.search(params)
            flights = []
            for r in results[:10]:
                flights.append({
                    "route": f"{r.origin} -> {r.destination}",
                    "price": f"{r.currency} {r.price:,.0f}",
                    "duration": f"{r.total_duration_minutes // 60}h {r.total_duration_minutes % 60}m",
                    "stops": r.num_stops,
                    "carriers": ", ".join(set(l.carrier for l in r.legs if l.carrier)),
                    "departure": r.departure.isoformat() if r.departure else "N/A",
                    "provider": r.provider,
                })
            return json.dumps({"flights": flights, "count": len(flights)})
        finally:
            await orchestrator.close()

    elif name == "search_airport":
        db = await get_airport_db(config.data_dir)
        results = db.search(arguments["query"])[:10]
        airports = [{"iata": a.iata, "name": a.name, "city": a.city, "country": a.country_code} for a in results]
        return json.dumps({"airports": airports})

    elif name == "find_routes":
        db = await get_airport_db(config.data_dir)
        graph = RouteGraph(db)
        avoid = arguments.get("avoid_zones", [])
        graph.build(avoid_zones=avoid or None)
        solver = RouteSolver(graph, db)
        routes = solver.find_routes_avoiding_zones(
            arguments["origin"].upper(),
            arguments["destination"].upper(),
            avoid,
            max_stops=arguments.get("max_stops", 3),
        )
        result = []
        for path in routes[:10]:
            result.append({
                "route": " -> ".join(path),
                "stops": len(path) - 2,
                "distance_km": round(graph.path_distance(path)),
            })
        return json.dumps({"routes": result, "count": len(result)})

    elif name == "compare_departure_airports":
        db = await get_airport_db(config.data_dir)
        graph = RouteGraph(db)
        avoid = arguments.get("avoid_zones", [])
        graph.build(avoid_zones=avoid or None)
        solver = RouteSolver(graph, db)
        suggestions = solver.suggest_departure_airports(
            [a.upper() for a in arguments["airports"]],
            arguments["destination"].upper(),
            avoid_zones=avoid,
        )
        for s in suggestions:
            if s.get("path_distance_km"):
                s["path_distance_km"] = round(s["path_distance_km"])
            if s.get("direct_distance_km"):
                s["direct_distance_km"] = round(s["direct_distance_km"])
        return json.dumps({"suggestions": suggestions})

    elif name == "optimize_route":
        db = await get_airport_db(config.data_dir)
        graph = RouteGraph(db)
        graph.build()
        solver = RouteSolver(graph, db)
        result = solver.solve_optimal_order(
            arguments["origin"].upper(),
            arguments["destination"].upper(),
            [w.upper() for w in arguments["waypoints"]],
        )
        if result:
            return json.dumps({
                "optimal_route": " -> ".join(result.stops),
                "total_distance_km": round(result.total_distance_km),
                "legs": result.legs,
            })
        return json.dumps({"error": "No viable route found"})

    return json.dumps({"error": f"Unknown tool: {name}"})
