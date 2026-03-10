"""Amadeus GDS provider using the official Python SDK."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from voyagair.core.providers.base import Provider, ProviderError
from voyagair.core.search.models import CabinClass, FlightOffer, Leg, SearchParams, TransportMode

logger = logging.getLogger(__name__)

CABIN_MAP = {
    CabinClass.ECONOMY: "ECONOMY",
    CabinClass.PREMIUM_ECONOMY: "PREMIUM_ECONOMY",
    CabinClass.BUSINESS: "BUSINESS",
    CabinClass.FIRST: "FIRST",
}


class AmadeusProvider(Provider):
    """Search flights via the Amadeus Self-Service API."""

    name = "amadeus"
    supports_multimodal = False

    def __init__(self, client_id: str, client_secret: str, environment: str = "test"):
        self._client_id = client_id
        self._client_secret = client_secret
        self._environment = environment
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from amadeus import Client, ResponseError

                hostname = "test" if self._environment == "test" else "production"
                self._client = Client(
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    hostname=hostname,
                    logger=logger,
                )
            except ImportError:
                raise ProviderError(self.name, "amadeus package not installed. Run: pip install amadeus")
        return self._client

    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in params.origins:
            for destination in params.destinations:
                for dep_date in params.departure_dates:
                    try:
                        batch = await self._search_single(
                            origin, destination, dep_date.isoformat(),
                            params.adults, params.cabin_class, params.currency,
                            params.max_stops,
                        )
                        offers.extend(batch)
                    except Exception as e:
                        logger.warning("Amadeus search failed for %s->%s: %s", origin, destination, e)
        return offers[:params.limit]

    async def _search_single(
        self,
        origin: str,
        destination: str,
        date_str: str,
        adults: int,
        cabin: CabinClass,
        currency: str,
        max_stops: int | None,
    ) -> list[FlightOffer]:
        client = self._get_client()

        kwargs: dict = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": date_str,
            "adults": adults,
            "currencyCode": currency,
            "max": 50,
        }
        if cabin != CabinClass.ECONOMY:
            kwargs["travelClass"] = CABIN_MAP[cabin]
        if max_stops is not None:
            kwargs["maxNumberOfConnections"] = max_stops

        def _do_search():
            return client.shopping.flight_offers_search.get(**kwargs)

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, _do_search)
        except Exception as e:
            raise ProviderError(self.name, f"API call failed: {e}")

        return self._parse_response(response.data if hasattr(response, "data") else [])

    def _parse_response(self, data: list) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for item in data:
            try:
                price = float(item.get("price", {}).get("total", 0))
                currency = item.get("price", {}).get("currency", "USD")

                legs: list[Leg] = []
                for itin in item.get("itineraries", []):
                    for segment in itin.get("segments", []):
                        dep = segment.get("departure", {})
                        arr = segment.get("arrival", {})
                        operating = segment.get("operating", {})

                        dep_time = datetime.fromisoformat(dep.get("at", ""))
                        arr_time = datetime.fromisoformat(arr.get("at", ""))

                        duration_str = segment.get("duration", "")
                        duration_min = self._parse_iso_duration(duration_str)

                        leg = Leg(
                            origin=dep.get("iataCode", ""),
                            destination=arr.get("iataCode", ""),
                            departure=dep_time,
                            arrival=arr_time,
                            carrier=segment.get("carrierCode", ""),
                            flight_number=f"{segment.get('carrierCode', '')}{segment.get('number', '')}",
                            mode=TransportMode.FLIGHT,
                            aircraft=segment.get("aircraft", {}).get("code", ""),
                            duration_minutes=duration_min,
                            stops=segment.get("numberOfStops", 0),
                        )
                        legs.append(leg)

                offer = FlightOffer(
                    id=item.get("id", str(uuid.uuid4())[:8]),
                    provider=self.name,
                    legs=legs,
                    price=price,
                    currency=currency,
                    raw_data=item,
                )
                offers.append(offer)
            except Exception as e:
                logger.debug("Failed to parse Amadeus result: %s", e)
                continue
        return offers

    @staticmethod
    def _parse_iso_duration(duration: str) -> int:
        """Parse ISO 8601 duration like 'PT2H30M' into minutes."""
        if not duration:
            return 0
        minutes = 0
        duration = duration.replace("PT", "").replace("P", "")
        if "H" in duration:
            parts = duration.split("H")
            try:
                minutes += int(parts[0]) * 60
            except ValueError:
                pass
            duration = parts[1] if len(parts) > 1 else ""
        if "M" in duration:
            try:
                minutes += int(duration.replace("M", ""))
            except ValueError:
                pass
        return minutes

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def close(self) -> None:
        self._client = None
