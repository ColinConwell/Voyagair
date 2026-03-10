"""Google Flights provider using the fast-flights scraper (no API key required)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from voyagair.core.providers.base import Provider, ProviderError
from voyagair.core.search.models import CabinClass, FlightOffer, Leg, SearchParams, TransportMode

logger = logging.getLogger(__name__)

SEAT_MAP = {
    CabinClass.ECONOMY: "economy",
    CabinClass.PREMIUM_ECONOMY: "premium-economy",
    CabinClass.BUSINESS: "business",
    CabinClass.FIRST: "first",
}


class GoogleFlightsProvider(Provider):
    """Search flights via Google Flights using the fast-flights scraper."""

    name = "google_flights"
    supports_multimodal = False

    def __init__(self, max_results: int = 50):
        self._max_results = max_results

    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        for origin in params.origins:
            for destination in params.destinations:
                for dep_date in params.departure_dates:
                    try:
                        batch = await self._search_single(
                            origin, destination, dep_date.isoformat(),
                            params.adults, params.cabin_class, params.currency,
                        )
                        offers.extend(batch)
                    except Exception as e:
                        logger.warning("Google Flights search failed for %s->%s: %s", origin, destination, e)
        return offers[:params.limit]

    async def _search_single(
        self, origin: str, destination: str, date_str: str,
        adults: int, cabin: CabinClass, currency: str,
    ) -> list[FlightOffer]:
        try:
            from fast_flights import FlightQuery, Passengers, create_query, get_flights
        except ImportError:
            raise ProviderError(self.name, "fast-flights not installed. Run: pip install faster-flights")

        seat = SEAT_MAP.get(cabin, "economy")

        def _do_search():
            fq = FlightQuery(
                date=date_str,
                from_airport=origin.upper(),
                to_airport=destination.upper(),
            )
            q = create_query(
                flights=[fq],
                passengers=Passengers(adults=adults),
                seat=seat,
                trip="one-way",
                currency=currency or "USD",
            )
            return get_flights(q)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _do_search)

        offers: list[FlightOffer] = []
        if not result:
            return offers

        for flight_group in result:
            try:
                legs: list[Leg] = []
                for single in (flight_group.flights or []):
                    dep_dt = self._parse_simple_datetime(single.departure)
                    arr_dt = self._parse_simple_datetime(single.arrival)

                    from_code = single.from_airport.code if single.from_airport else origin.upper()
                    to_code = single.to_airport.code if single.to_airport else destination.upper()

                    leg = Leg(
                        origin=from_code,
                        destination=to_code,
                        departure=dep_dt,
                        arrival=arr_dt,
                        carrier=single.airline_code or "",
                        carrier_name=(flight_group.airlines[0] if flight_group.airlines else ""),
                        flight_number=single.flight_number or "",
                        mode=TransportMode.FLIGHT,
                        aircraft=single.plane_type or "",
                        duration_minutes=single.duration or 0,
                    )
                    legs.append(leg)

                price = float(flight_group.price) if flight_group.price else 0.0
                num_stops = max(0, len(legs) - 1)

                co2 = None
                if flight_group.carbon and hasattr(flight_group.carbon, "emission"):
                    co2 = flight_group.carbon.emission / 1000.0 if flight_group.carbon.emission else None

                offer = FlightOffer(
                    id=str(uuid.uuid4())[:8],
                    provider=self.name,
                    legs=legs,
                    price=price,
                    currency=currency or "USD",
                    co2_kg=co2,
                )
                offers.append(offer)
            except Exception as e:
                logger.debug("Failed to parse Google Flights result: %s", e)
                continue

        return offers

    @staticmethod
    def _parse_simple_datetime(sdt) -> datetime:
        """Convert a fast_flights SimpleDatetime to a Python datetime."""
        if sdt is None:
            return datetime.now()
        try:
            d = sdt.date or [2026, 1, 1]
            t = sdt.time or [0, 0]
            return datetime(d[0], d[1], d[2], t[0], t[1])
        except (IndexError, TypeError, ValueError):
            return datetime.now()

    def is_configured(self) -> bool:
        try:
            import fast_flights  # noqa: F401
            return True
        except ImportError:
            return False
