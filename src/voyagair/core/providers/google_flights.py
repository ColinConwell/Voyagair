"""Google Flights provider using the faster-flights scraper (no API key required)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from voyagair.core.providers.base import Provider, ProviderError
from voyagair.core.search.models import CabinClass, FlightOffer, Leg, SearchParams, TransportMode

logger = logging.getLogger(__name__)

CABIN_MAP = {
    CabinClass.ECONOMY: 1,
    CabinClass.PREMIUM_ECONOMY: 2,
    CabinClass.BUSINESS: 3,
    CabinClass.FIRST: 4,
}


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string like '5h 30m' or '12 hr 5 min' into minutes."""
    if not duration_str:
        return 0
    minutes = 0
    parts = duration_str.lower().replace("hr", "h").replace("min", "m").split()
    for part in parts:
        part = part.strip()
        if "h" in part:
            try:
                minutes += int(part.replace("h", "").strip()) * 60
            except ValueError:
                pass
        elif "m" in part:
            try:
                minutes += int(part.replace("m", "").strip())
            except ValueError:
                pass
    return minutes


def _parse_price(price_str: str) -> float:
    """Parse a price string like '$1,234' into a float."""
    if not price_str:
        return 0.0
    cleaned = price_str.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class GoogleFlightsProvider(Provider):
    """Search flights via Google Flights using the faster-flights scraper."""

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
                            params.adults, params.cabin_class,
                        )
                        offers.extend(batch)
                    except Exception as e:
                        logger.warning("Google Flights search failed for %s->%s: %s", origin, destination, e)
        return offers[:params.limit]

    async def _search_single(
        self, origin: str, destination: str, date_str: str, adults: int, cabin: CabinClass
    ) -> list[FlightOffer]:
        try:
            from faster_flights import FlightData, Passengers, create_filter, get_flights
        except ImportError:
            raise ProviderError(self.name, "faster-flights not installed. Run: pip install faster-flights")

        def _do_search():
            flight_data = [FlightData(date=date_str, from_airport=origin.upper(), to_airport=destination.upper())]
            ft = create_filter(max_stops=None, trip="one-way")
            result = get_flights(flight_data=flight_data, passengers=Passengers(adults=adults), filter=ft)
            return result

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _do_search)

        offers: list[FlightOffer] = []
        if not result or not hasattr(result, "flights"):
            return offers

        for flight in result.flights:
            try:
                legs = []
                dep_time = getattr(flight, "departure", None)
                arr_time = getattr(flight, "arrival", None)
                if isinstance(dep_time, str):
                    try:
                        dep_time = datetime.fromisoformat(dep_time)
                    except ValueError:
                        dep_time = datetime.now()
                if isinstance(arr_time, str):
                    try:
                        arr_time = datetime.fromisoformat(arr_time)
                    except ValueError:
                        arr_time = datetime.now()
                if dep_time is None:
                    dep_time = datetime.now()
                if arr_time is None:
                    arr_time = dep_time

                duration = _parse_duration(getattr(flight, "duration", "") or "")
                name = getattr(flight, "name", "") or ""
                stops = getattr(flight, "stops", 0)
                if isinstance(stops, str):
                    stops = int(stops) if stops.isdigit() else 0

                leg = Leg(
                    origin=origin.upper(),
                    destination=destination.upper(),
                    departure=dep_time,
                    arrival=arr_time,
                    carrier=name.split(" ")[0] if name else "",
                    carrier_name=name,
                    mode=TransportMode.FLIGHT,
                    duration_minutes=duration,
                    stops=stops if isinstance(stops, int) else 0,
                )
                legs.append(leg)

                price = _parse_price(getattr(flight, "price", "") or "")
                offer = FlightOffer(
                    id=str(uuid.uuid4())[:8],
                    provider=self.name,
                    legs=legs,
                    price=price,
                    currency="USD",
                    deep_link=getattr(flight, "url", "") or "",
                )
                offers.append(offer)
            except Exception as e:
                logger.debug("Failed to parse Google Flights result: %s", e)
                continue

        return offers

    def is_configured(self) -> bool:
        try:
            import faster_flights  # noqa: F401
            return True
        except ImportError:
            return False
