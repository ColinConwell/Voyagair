"""Pydantic data models for airports, flights, legs, itineraries, and search parameters."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransportMode(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    FERRY = "ferry"
    RIDESHARE = "rideshare"
    UNKNOWN = "unknown"


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class SortKey(str, Enum):
    PRICE = "price"
    DURATION = "duration"
    DEPARTURE = "departure"
    ARRIVAL = "arrival"
    STOPS = "stops"


class Airport(BaseModel):
    iata: str
    icao: str = ""
    name: str = ""
    city: str = ""
    country: str = ""
    country_code: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = ""
    airport_type: str = ""

    def __hash__(self) -> int:
        return hash(self.iata)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Airport):
            return self.iata == other.iata
        return NotImplemented


class Leg(BaseModel):
    """A single segment of travel (one takeoff/boarding to one landing/arrival)."""

    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    carrier: str = ""
    carrier_name: str = ""
    flight_number: str = ""
    mode: TransportMode = TransportMode.FLIGHT
    aircraft: str = ""
    cabin_class: CabinClass = CabinClass.ECONOMY
    duration_minutes: int = 0
    stops: int = 0

    @property
    def duration(self) -> timedelta:
        if self.duration_minutes > 0:
            return timedelta(minutes=self.duration_minutes)
        return self.arrival - self.departure


class FlightOffer(BaseModel):
    """A complete flight offer, potentially with multiple legs (connections)."""

    id: str = ""
    provider: str = ""
    legs: list[Leg] = Field(default_factory=list)
    price: float = 0.0
    currency: str = "USD"
    deep_link: str = ""
    booking_url: str = ""
    cabin_class: CabinClass = CabinClass.ECONOMY
    baggage_included: bool = False
    co2_kg: float | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def origin(self) -> str:
        return self.legs[0].origin if self.legs else ""

    @property
    def destination(self) -> str:
        return self.legs[-1].destination if self.legs else ""

    @property
    def departure(self) -> datetime | None:
        return self.legs[0].departure if self.legs else None

    @property
    def arrival(self) -> datetime | None:
        return self.legs[-1].arrival if self.legs else None

    @property
    def total_duration_minutes(self) -> int:
        if not self.legs:
            return 0
        total = sum(leg.duration.total_seconds() for leg in self.legs)
        if len(self.legs) > 1:
            for i in range(len(self.legs) - 1):
                layover = (self.legs[i + 1].departure - self.legs[i].arrival).total_seconds()
                total += max(0, layover)
        return int(total / 60)

    @property
    def num_stops(self) -> int:
        return max(0, len(self.legs) - 1)


class TransportOption(BaseModel):
    """A non-flight transport option (train, bus, ferry, etc.)."""

    origin: str
    destination: str
    mode: TransportMode
    carrier: str = ""
    departure: datetime | None = None
    arrival: datetime | None = None
    duration_minutes: int = 0
    price_min: float | None = None
    price_max: float | None = None
    currency: str = "USD"
    booking_url: str = ""
    frequency: str = ""


class Itinerary(BaseModel):
    """A full multi-stop itinerary composed of multiple offers/options."""

    id: str = ""
    segments: list[FlightOffer | TransportOption] = Field(default_factory=list)
    total_price: float = 0.0
    currency: str = "USD"
    total_duration_minutes: int = 0
    stops: list[str] = Field(default_factory=list)

    def compute_totals(self) -> None:
        self.total_price = 0.0
        self.total_duration_minutes = 0
        self.stops = []
        for seg in self.segments:
            if isinstance(seg, FlightOffer):
                self.total_price += seg.price
                self.total_duration_minutes += seg.total_duration_minutes
                if seg.origin:
                    self.stops.append(seg.origin)
            elif isinstance(seg, TransportOption):
                self.total_price += seg.price_min or 0.0
                self.total_duration_minutes += seg.duration_minutes
                if seg.origin:
                    self.stops.append(seg.origin)
        if self.segments:
            last = self.segments[-1]
            dest = last.destination if isinstance(last, FlightOffer) else last.destination
            if dest:
                self.stops.append(dest)


class SearchParams(BaseModel):
    """Parameters for a flight/transport search."""

    origins: list[str] = Field(min_length=1)
    destinations: list[str] = Field(min_length=1)
    departure_dates: list[date] = Field(min_length=1)
    return_dates: list[date] | None = None
    adults: int = 1
    children: int = 0
    cabin_class: CabinClass = CabinClass.ECONOMY
    max_price: float | None = None
    max_stops: int | None = None
    max_duration_hours: int | None = None
    currency: str = "USD"
    sort_by: SortKey = SortKey.PRICE
    limit: int = 50
    providers: list[str] | None = None


class MultiStopParams(BaseModel):
    """Parameters for multi-stop trip planning."""

    origin: str
    destination: str
    waypoints: list[str] = Field(default_factory=list)
    departure_date_start: date
    departure_date_end: date | None = None
    min_stay_days: int = 1
    max_stay_days: int = 7
    budget: float | None = None
    currency: str = "USD"
    avoid_regions: list[str] = Field(default_factory=list)
    adults: int = 1
    cabin_class: CabinClass = CabinClass.ECONOMY
    optimize_for: SortKey = SortKey.PRICE
