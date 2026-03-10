"""Airport data API endpoints with autocomplete support."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db
from voyagair.core.voyage.resolver import REGION_MAP

router = APIRouter()


@router.get("/search")
async def search_airports(
    q: str = Query(..., description="Search query (IATA, name, or city)"),
    limit: int = Query(20, le=100),
    region: Optional[str] = Query(None, description="Filter by region name (e.g. Europe, Southeast Asia)"),
    grouped: bool = Query(False, description="Return results grouped by match type for autocomplete"),
):
    """Search for airports by IATA code, name, or city, with optional region filter."""
    config = get_config()
    db = await get_airport_db(config.data_dir)

    if region:
        region_key = None
        for key in REGION_MAP:
            if key.lower() == region.lower():
                region_key = key
                break
        if region_key:
            country_codes = REGION_MAP[region_key]
            region_airports = []
            for cc in country_codes:
                region_airports.extend(db.get_by_country(cc))
            ql = q.lower().strip()
            results = [
                a for a in region_airports
                if ql in a.iata.lower() or ql in a.name.lower() or ql in a.city.lower()
            ][:limit]
        else:
            results = db.search(q)[:limit]
    else:
        results = db.search(q)[:limit]

    if not grouped:
        return {"results": [r.model_dump() for r in results], "count": len(results)}

    groups: dict[str, list] = {
        "airports": [],
        "cities": [],
        "countries": [],
        "regions": [],
    }

    q_upper = q.strip().upper()
    q_lower = q.strip().lower()

    for r in results:
        entry = r.model_dump()
        if r.iata == q_upper or r.icao == q_upper:
            groups["airports"].insert(0, entry)
        elif q_lower == r.city.lower():
            groups["cities"].append(entry)
        else:
            groups["airports"].append(entry)

    seen_countries: set[str] = set()
    for r in results:
        if r.country_code and r.country_code not in seen_countries:
            if q_lower in r.country.lower() or q_upper == r.country_code:
                seen_countries.add(r.country_code)
                groups["countries"].append({
                    "country_code": r.country_code,
                    "country": r.country,
                    "airport_count": len(db.get_by_country(r.country_code)),
                })

    seen_cities: set[str] = set()
    for r in results:
        city_key = r.city.lower()
        if city_key and city_key not in seen_cities and q_lower in city_key:
            seen_cities.add(city_key)
            city_airports = db.get_by_city(city_key)
            if len(city_airports) > 1:
                groups["cities"].append({
                    "city": r.city,
                    "country_code": r.country_code,
                    "airport_count": len(city_airports),
                })

    for region_name in REGION_MAP:
        if q_lower in region_name.lower():
            groups["regions"].append({
                "region": region_name,
                "country_count": len(REGION_MAP[region_name]),
            })

    return {"groups": groups, "total": len(results)}


@router.get("/regions")
async def list_regions():
    """List all known geographic regions and their country codes."""
    return {
        "regions": [
            {"name": name, "country_count": len(codes)}
            for name, codes in sorted(REGION_MAP.items())
        ]
    }


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
