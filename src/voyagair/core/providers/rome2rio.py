"""Rome2Rio provider for multi-modal transport discovery (flights, trains, buses, ferries)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import httpx

from voyagair.core.providers.base import Provider, ProviderError
from voyagair.core.search.models import (
    FlightOffer,
    Leg,
    SearchParams,
    TransportMode,
    TransportOption,
)

logger = logging.getLogger(__name__)

R2R_BASE = "https://free.rome2rio.com/api/1.4/json"

MODE_MAP = {
    "flight": TransportMode.FLIGHT,
    "train": TransportMode.TRAIN,
    "bus": TransportMode.BUS,
    "ferry": TransportMode.FERRY,
    "rideshare": TransportMode.RIDESHARE,
}


class Rome2RioProvider(Provider):
    """Multi-modal transport search via Rome2Rio API."""

    name = "rome2rio"
    supports_multimodal = True

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        """Rome2Rio doesn't return bookable flight offers; returns empty list."""
        return []

    async def search_transport(self, params: SearchParams) -> list[TransportOption]:
        options: list[TransportOption] = []
        for origin in params.origins:
            for destination in params.destinations:
                try:
                    batch = await self._search_single(origin, destination, params.currency)
                    options.extend(batch)
                except Exception as e:
                    logger.warning("Rome2Rio search failed for %s->%s: %s", origin, destination, e)
        return options

    async def _search_single(
        self, origin: str, destination: str, currency: str
    ) -> list[TransportOption]:
        query_params = {
            "key": self._api_key,
            "oName": origin,
            "dName": destination,
            "currencyCode": currency,
            "noAir": "false",
            "noRail": "false",
            "noBus": "false",
            "noFerry": "false",
        }

        try:
            resp = await self._client.get(f"{R2R_BASE}/Search", params=query_params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"API returned {e.response.status_code}")
        except Exception as e:
            raise ProviderError(self.name, f"Request failed: {e}")

        return self._parse_response(data, origin, destination, currency)

    def _parse_response(
        self, data: dict, origin: str, destination: str, currency: str
    ) -> list[TransportOption]:
        options: list[TransportOption] = []
        for route in data.get("routes", []):
            route_name = route.get("name", "")
            mode_str = route_name.lower().split(",")[0].strip() if route_name else "unknown"
            mode = TransportMode.UNKNOWN
            for key, val in MODE_MAP.items():
                if key in mode_str:
                    mode = val
                    break

            duration_min = route.get("totalDuration", 0)
            price_data = route.get("indicativePrices", [{}])
            price_min = None
            price_max = None
            if price_data:
                p = price_data[0]
                price_min = p.get("priceLow") or p.get("price")
                price_max = p.get("priceHigh") or p.get("price")
                if price_min is not None:
                    price_min = float(price_min)
                if price_max is not None:
                    price_max = float(price_max)

            frequency = ""
            segments = route.get("segments", [])
            if segments:
                freq = segments[0].get("frequency", "")
                if freq:
                    frequency = freq

            option = TransportOption(
                origin=origin,
                destination=destination,
                mode=mode,
                carrier=route_name,
                duration_minutes=int(duration_min),
                price_min=price_min,
                price_max=price_max,
                currency=currency,
                frequency=frequency,
            )
            options.append(option)
        return options

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def close(self) -> None:
        await self._client.aclose()
