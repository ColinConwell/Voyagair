"""Kiwi.com Tequila API provider for flight search and virtual interlining."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import httpx

from voyagair.core.providers.base import Provider, ProviderError
from voyagair.core.search.models import CabinClass, FlightOffer, Leg, SearchParams, TransportMode

logger = logging.getLogger(__name__)

TEQUILA_BASE = "https://api.tequila.kiwi.com/v2"

CABIN_MAP = {
    CabinClass.ECONOMY: "M",
    CabinClass.PREMIUM_ECONOMY: "W",
    CabinClass.BUSINESS: "C",
    CabinClass.FIRST: "F",
}


class KiwiProvider(Provider):
    """Search flights via Kiwi.com Tequila API (supports virtual interlining)."""

    name = "kiwi"
    supports_multimodal = True

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=TEQUILA_BASE,
            headers={"apikey": api_key},
            timeout=timeout,
            follow_redirects=True,
        )

    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in params.origins:
            for destination in params.destinations:
                for dep_date in params.departure_dates:
                    try:
                        batch = await self._search_single(
                            origin, destination, dep_date,
                            params.adults, params.cabin_class, params.currency,
                            params.max_stops, params.limit,
                        )
                        offers.extend(batch)
                    except Exception as e:
                        logger.warning("Kiwi search failed for %s->%s: %s", origin, destination, e)
        return offers[:params.limit]

    async def _search_single(
        self,
        origin: str,
        destination: str,
        dep_date,
        adults: int,
        cabin: CabinClass,
        currency: str,
        max_stops: int | None,
        limit: int,
    ) -> list[FlightOffer]:
        date_str = dep_date.strftime("%d/%m/%Y") if hasattr(dep_date, "strftime") else str(dep_date)

        query_params = {
            "fly_from": origin.upper(),
            "fly_to": destination.upper(),
            "date_from": date_str,
            "date_to": date_str,
            "adults": adults,
            "curr": currency,
            "limit": limit,
            "sort": "price",
            "selected_cabins": CABIN_MAP.get(cabin, "M"),
            "vehicle_type": "aircraft",
        }
        if max_stops is not None:
            query_params["max_stopovers"] = max_stops

        try:
            resp = await self._client.get("/search", params=query_params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"API returned {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise ProviderError(self.name, f"Request failed: {e}")

        return self._parse_response(data, currency)

    def _parse_response(self, data: dict, currency: str) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for item in data.get("data", []):
            try:
                legs: list[Leg] = []
                for route in item.get("route", []):
                    dep_time = datetime.fromtimestamp(route.get("dTime", 0))
                    arr_time = datetime.fromtimestamp(route.get("aTime", 0))
                    duration_sec = route.get("fly_duration", 0)
                    if isinstance(duration_sec, str):
                        duration_min = 0
                    else:
                        duration_min = int(duration_sec / 60) if duration_sec else 0

                    leg = Leg(
                        origin=route.get("flyFrom", ""),
                        destination=route.get("flyTo", ""),
                        departure=dep_time,
                        arrival=arr_time,
                        carrier=route.get("airline", ""),
                        flight_number=f"{route.get('airline', '')}{route.get('flight_no', '')}",
                        mode=TransportMode.FLIGHT,
                        duration_minutes=duration_min,
                    )
                    legs.append(leg)

                price = float(item.get("price", 0))
                offer = FlightOffer(
                    id=item.get("id", str(uuid.uuid4())[:8]),
                    provider=self.name,
                    legs=legs,
                    price=price,
                    currency=currency,
                    deep_link=item.get("deep_link", ""),
                    booking_url=item.get("deep_link", ""),
                    raw_data=item,
                )
                offers.append(offer)
            except Exception as e:
                logger.debug("Failed to parse Kiwi result: %s", e)
                continue
        return offers

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def close(self) -> None:
        await self._client.aclose()
