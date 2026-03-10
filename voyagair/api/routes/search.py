"""Search API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from voyagair.api.deps import get_orchestrator
from voyagair.core.search.models import CabinClass, FlightOffer, SearchParams, SortKey

router = APIRouter()


class SearchRequest(BaseModel):
    origins: list[str]
    destinations: list[str]
    departure_dates: list[date]
    return_dates: list[date] | None = None
    adults: int = 1
    cabin_class: CabinClass = CabinClass.ECONOMY
    max_price: float | None = None
    max_stops: int | None = None
    max_duration_hours: int | None = None
    currency: str = "USD"
    sort_by: SortKey = SortKey.PRICE
    limit: int = 50
    providers: list[str] | None = None


class SearchResponse(BaseModel):
    results: list[FlightOffer]
    count: int
    cached: bool = False


@router.post("/flights", response_model=SearchResponse)
async def search_flights(request: SearchRequest):
    """Search for flights across all configured providers."""
    params = SearchParams(**request.model_dump())
    orchestrator = get_orchestrator()
    results = await orchestrator.search(params)
    return SearchResponse(results=results, count=len(results))


@router.get("/flights")
async def search_flights_get(
    origin: str = Query(..., description="Origin airport IATA code"),
    destination: str = Query(..., description="Destination airport IATA code"),
    date: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    adults: int = Query(1),
    cabin: str = Query("economy"),
    max_price: Optional[float] = Query(None),
    max_stops: Optional[int] = Query(None),
    sort: str = Query("price"),
    limit: int = Query(20),
    currency: str = Query("USD"),
):
    """Search flights via GET (simpler interface)."""
    try:
        cabin_class = CabinClass(cabin.lower())
    except ValueError:
        cabin_class = CabinClass.ECONOMY

    try:
        sort_key = SortKey(sort.lower())
    except ValueError:
        sort_key = SortKey.PRICE

    params = SearchParams(
        origins=[origin.upper()],
        destinations=[destination.upper()],
        departure_dates=[date_obj] if (date_obj := __import__("datetime").date.fromisoformat(date)) else [],
        adults=adults,
        cabin_class=cabin_class,
        max_price=max_price,
        max_stops=max_stops,
        currency=currency,
        sort_by=sort_key,
        limit=limit,
    )
    orchestrator = get_orchestrator()
    results = await orchestrator.search(params)
    return {"results": [r.model_dump() for r in results], "count": len(results)}
