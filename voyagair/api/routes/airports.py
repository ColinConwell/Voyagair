"""Airport data API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db

router = APIRouter()


@router.get("/search")
async def search_airports(
    q: str = Query(..., description="Search query (IATA, name, or city)"),
    limit: int = Query(20, le=100),
):
    """Search for airports by IATA code, name, or city."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    results = db.search(q)[:limit]
    return {"results": [r.model_dump() for r in results], "count": len(results)}


@router.get("/country/{country_code}")
async def airports_by_country(country_code: str, limit: int = Query(50, le=200)):
    """Get airports in a specific country."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    results = db.get_by_country(country_code.upper())[:limit]
    return {"results": [r.model_dump() for r in results], "count": len(results)}


@router.get("/{iata}")
async def get_airport(iata: str):
    """Get details for a specific airport by IATA code."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    airport = db.get(iata.upper())
    if airport:
        return airport.model_dump()
    return {"error": f"Airport {iata.upper()} not found"}


@router.get("/{iata}/routes")
async def get_routes(iata: str, direction: str = Query("from", enum=["from", "to"])):
    """Get direct routes from/to an airport."""
    config = get_config()
    db = await get_airport_db(config.data_dir)
    if direction == "from":
        routes = db.get_routes_from(iata.upper())
    else:
        routes = db.get_routes_to(iata.upper())
    return {
        "airport": iata.upper(),
        "direction": direction,
        "routes": [{"airport": r[0], "airline": r[1]} for r in routes],
        "count": len(routes),
    }
