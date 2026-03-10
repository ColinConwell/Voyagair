"""Configuration and API key management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    enabled: bool = True
    rate_limit: int = 10
    rate_period: float = 1.0
    timeout: float = 30.0
    extra: dict[str, Any] = Field(default_factory=dict)


class AmadeusConfig(ProviderConfig):
    client_id: str = ""
    client_secret: str = ""
    environment: str = "test"

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


class KiwiConfig(ProviderConfig):
    api_key: str = ""

    def is_configured(self) -> bool:
        return bool(self.api_key)


class Rome2RioConfig(ProviderConfig):
    api_key: str = ""

    def is_configured(self) -> bool:
        return bool(self.api_key)


class GoogleFlightsConfig(ProviderConfig):
    """No API key needed -- uses scraping via faster-flights."""

    max_results: int = 50

    def is_configured(self) -> bool:
        return True


class SerpAPIConfig(ProviderConfig):
    api_key: str = ""

    def is_configured(self) -> bool:
        return bool(self.api_key)


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    temperature: float = 0.3


class CacheConfig(BaseModel):
    directory: str = ".voyagair_cache"
    ttl_seconds: int = 3600
    max_size_mb: int = 500


class VoyagairConfig(BaseModel):
    amadeus: AmadeusConfig = Field(default_factory=AmadeusConfig)
    kiwi: KiwiConfig = Field(default_factory=KiwiConfig)
    rome2rio: Rome2RioConfig = Field(default_factory=Rome2RioConfig)
    google_flights: GoogleFlightsConfig = Field(default_factory=GoogleFlightsConfig)
    serpapi: SerpAPIConfig = Field(default_factory=SerpAPIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    data_dir: str = str(Path(__file__).parent.parent.parent.parent / "data")

    @classmethod
    def from_env(cls) -> VoyagairConfig:
        """Load configuration from environment variables."""
        return cls(
            amadeus=AmadeusConfig(
                client_id=os.getenv("AMADEUS_CLIENT_ID", ""),
                client_secret=os.getenv("AMADEUS_CLIENT_SECRET", ""),
                environment=os.getenv("AMADEUS_ENVIRONMENT", "test"),
            ),
            kiwi=KiwiConfig(
                api_key=os.getenv("KIWI_API_KEY", ""),
            ),
            rome2rio=Rome2RioConfig(
                api_key=os.getenv("ROME2RIO_API_KEY", ""),
            ),
            google_flights=GoogleFlightsConfig(),
            serpapi=SerpAPIConfig(
                api_key=os.getenv("SERPAPI_KEY", ""),
            ),
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "openai"),
                model=os.getenv("LLM_MODEL", "gpt-4o"),
                api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            ),
            cache=CacheConfig(
                directory=os.getenv("VOYAGAIR_CACHE_DIR", ".voyagair_cache"),
            ),
        )


_config: VoyagairConfig | None = None


def get_config() -> VoyagairConfig:
    global _config
    if _config is None:
        _config = VoyagairConfig.from_env()
    return _config


def set_config(config: VoyagairConfig) -> None:
    global _config
    _config = config
