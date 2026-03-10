"""Voyage configuration and results data models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from voyagair.core.search.models import (
    CabinClass,
    FlightOffer,
    Itinerary,
    SortKey,
    TransportOption,
)


class LocationType(str, Enum):
    REGION = "region"
    COUNTRY = "country"
    CITY = "city"
    AIRPORT = "airport"


class LocationSpec(BaseModel):
    """A polymorphic location specifier: region, country, city, or airport code."""

    type: LocationType
    value: str
    label: str = ""
    resolved_airports: list[str] = Field(default_factory=list)


class TimeBudget(BaseModel):
    total_days: int = 14
    max_journey_hours: float | None = None
    max_multi_ticket_hours: float | None = None


class CostBudget(BaseModel):
    max_total: float | None = None
    max_per_leg: float | None = None
    max_single_ticket: float | None = None
    max_multi_ticket_total: float | None = None
    currency: str = "USD"


class NotificationType(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    WEBAPP = "webapp"


class NotificationConfig(BaseModel):
    type: NotificationType
    target: str = ""
    enabled: bool = True


class SaveRefreshConfig(BaseModel):
    auto_save: bool = True
    save_path: str | None = None
    notifications: list[NotificationConfig] = Field(default_factory=list)
    auto_refresh_interval_minutes: int | None = None
    auto_refresh_enabled: bool = False


class MCPServerConfig(BaseModel):
    name: str
    url: str = ""
    auth_token: str = ""
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class TravelAgentConfig(BaseModel):
    enabled: bool = False
    use_builtin_tools: bool = True
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    custom_instructions: str | None = None
    model: str | None = None
    provider: str | None = None


class VoyageConfig(BaseModel):
    """Master configuration for a Voyage search."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Voyage"
    starting_points: list[LocationSpec] = Field(default_factory=list)
    end_points: list[LocationSpec] = Field(default_factory=list)
    sites_along_the_way: list[LocationSpec] = Field(default_factory=list)
    departure_date: str | None = None
    return_date: str | None = None
    flexible_dates: bool = False
    adults: int = 1
    cabin_class: CabinClass = CabinClass.ECONOMY
    time_budget: TimeBudget = Field(default_factory=TimeBudget)
    cost_budget: CostBudget = Field(default_factory=CostBudget)
    avoid_airlines: list[str] = Field(default_factory=list)
    avoid_routing_regions: list[str] = Field(default_factory=list)
    layover_regions: list[str] = Field(default_factory=list)
    notes: str | None = None
    travel_agent: TravelAgentConfig = Field(default_factory=TravelAgentConfig)
    save_refresh: SaveRefreshConfig = Field(default_factory=SaveRefreshConfig)
    optimize_for: SortKey = SortKey.PRICE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VoyageResults(BaseModel):
    """Container for voyage search results."""

    voyage_id: str = ""
    flight_options: list[FlightOffer] = Field(default_factory=list)
    transport_options: list[TransportOption] = Field(default_factory=list)
    itineraries: list[Itinerary] = Field(default_factory=list)
    agent_summary: str | None = None
    travel_agent_findings: dict | None = None
    searched_at: datetime = Field(default_factory=datetime.utcnow)
    search_duration_seconds: float = 0.0
