"""Abstract provider interface for flight/transport data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from voyagair.core.search.models import FlightOffer, SearchParams, TransportOption


class ProviderError(Exception):
    """Raised when a provider encounters an error."""

    def __init__(self, provider: str, message: str, raw: Any = None):
        self.provider = provider
        self.raw = raw
        super().__init__(f"[{provider}] {message}")


class Provider(ABC):
    """Base class for all travel data providers."""

    name: str = "base"
    supports_multimodal: bool = False

    @abstractmethod
    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        """Search for flight offers matching the given parameters."""
        ...

    async def search_transport(self, params: SearchParams) -> list[TransportOption]:
        """Search for non-flight transport options. Override in multimodal providers."""
        return []

    async def health_check(self) -> bool:
        """Check if the provider is available and configured."""
        return True

    async def close(self) -> None:
        """Clean up resources (HTTP clients, etc.)."""
        pass

    def is_configured(self) -> bool:
        """Whether this provider has the necessary credentials."""
        return True
