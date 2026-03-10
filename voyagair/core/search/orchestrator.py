"""Search orchestrator: fans out queries to all configured providers, deduplicates, and merges."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

from voyagair.core.cache import SearchCache, get_cache
from voyagair.core.config import VoyagairConfig, get_config
from voyagair.core.providers.base import Provider
from voyagair.core.rate_limiter import ProviderRateLimiter, get_rate_limiter
from voyagair.core.search.filters import deduplicate_offers, filter_offers, sort_offers
from voyagair.core.search.models import FlightOffer, SearchParams, SortKey, TransportOption

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Coordinates concurrent flight searches across multiple providers."""

    def __init__(
        self,
        providers: list[Provider] | None = None,
        config: VoyagairConfig | None = None,
        cache: SearchCache | None = None,
        rate_limiter: ProviderRateLimiter | None = None,
    ):
        self._config = config or get_config()
        self._cache = cache or get_cache(
            cache_dir=self._config.cache.directory,
            ttl=self._config.cache.ttl_seconds,
        )
        self._rate_limiter = rate_limiter or get_rate_limiter()
        self._providers: list[Provider] = providers or []

    def add_provider(self, provider: Provider) -> None:
        self._providers.append(provider)

    @classmethod
    def from_config(cls, config: VoyagairConfig | None = None) -> SearchOrchestrator:
        """Build an orchestrator with all configured providers."""
        config = config or get_config()
        orchestrator = cls(config=config)

        if config.google_flights.enabled and config.google_flights.is_configured():
            from voyagair.core.providers.google_flights import GoogleFlightsProvider
            orchestrator.add_provider(GoogleFlightsProvider(
                max_results=config.google_flights.max_results,
            ))
            orchestrator._rate_limiter.register(
                "google_flights",
                config.google_flights.rate_limit,
                config.google_flights.rate_period,
            )

        if config.amadeus.enabled and config.amadeus.is_configured():
            from voyagair.core.providers.amadeus_provider import AmadeusProvider
            orchestrator.add_provider(AmadeusProvider(
                client_id=config.amadeus.client_id,
                client_secret=config.amadeus.client_secret,
                environment=config.amadeus.environment,
            ))
            orchestrator._rate_limiter.register(
                "amadeus",
                config.amadeus.rate_limit,
                config.amadeus.rate_period,
            )

        if config.kiwi.enabled and config.kiwi.is_configured():
            from voyagair.core.providers.kiwi import KiwiProvider
            orchestrator.add_provider(KiwiProvider(
                api_key=config.kiwi.api_key,
                timeout=config.kiwi.timeout,
            ))
            orchestrator._rate_limiter.register(
                "kiwi",
                config.kiwi.rate_limit,
                config.kiwi.rate_period,
            )

        if config.rome2rio.enabled and config.rome2rio.is_configured():
            from voyagair.core.providers.rome2rio import Rome2RioProvider
            orchestrator.add_provider(Rome2RioProvider(
                api_key=config.rome2rio.api_key,
                timeout=config.rome2rio.timeout,
            ))
            orchestrator._rate_limiter.register(
                "rome2rio",
                config.rome2rio.rate_limit,
                config.rome2rio.rate_period,
            )

        return orchestrator

    async def search(self, params: SearchParams) -> list[FlightOffer]:
        """Search all providers concurrently, returning deduplicated and sorted results."""
        cache_key = self._cache.make_key(
            "search",
            origins=params.origins,
            destinations=params.destinations,
            dates=[d.isoformat() for d in params.departure_dates],
            adults=params.adults,
            cabin=params.cabin_class.value,
            providers=[p.name for p in self._providers],
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for search key %s", cache_key)
            return cached

        start = time.monotonic()
        tasks = []
        for provider in self._providers:
            if params.providers and provider.name not in params.providers:
                continue
            if not provider.is_configured():
                logger.warning("Provider %s is not configured, skipping", provider.name)
                continue
            tasks.append(self._search_provider(provider, params))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_offers: list[FlightOffer] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("Provider search failed: %s", result)
                continue
            all_offers.extend(result)

        all_offers = deduplicate_offers(all_offers)
        all_offers = filter_offers(
            all_offers,
            max_price=params.max_price,
            max_stops=params.max_stops,
            max_duration_hours=params.max_duration_hours,
        )
        all_offers = sort_offers(all_offers, params.sort_by)
        all_offers = all_offers[:params.limit]

        elapsed = time.monotonic() - start
        logger.info("Search completed in %.2fs: %d results from %d providers", elapsed, len(all_offers), len(tasks))

        if all_offers:
            self._cache.set(cache_key, all_offers)

        return all_offers

    async def search_transport(self, params: SearchParams) -> list[TransportOption]:
        """Search multimodal providers for non-flight transport options."""
        tasks = []
        for provider in self._providers:
            if provider.supports_multimodal and provider.is_configured():
                tasks.append(self._search_transport_provider(provider, params))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_options: list[TransportOption] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("Transport search failed: %s", result)
                continue
            all_options.extend(result)
        return all_options

    async def search_streaming(self, params: SearchParams) -> AsyncIterator[FlightOffer]:
        """Yield results as they arrive from each provider (for WebSocket streaming)."""
        queue: asyncio.Queue[FlightOffer | None] = asyncio.Queue()
        active_count = 0

        async def _worker(provider: Provider):
            nonlocal active_count
            try:
                await self._rate_limiter.acquire(provider.name)
                results = await provider.search_flights(params)
                for offer in results:
                    await queue.put(offer)
            except Exception as e:
                logger.error("Streaming search failed for %s: %s", provider.name, e)
            finally:
                await queue.put(None)

        providers = [
            p for p in self._providers
            if p.is_configured() and (not params.providers or p.name in params.providers)
        ]
        active_count = len(providers)

        for provider in providers:
            asyncio.create_task(_worker(provider))

        finished = 0
        seen: set[str] = set()
        while finished < active_count:
            item = await queue.get()
            if item is None:
                finished += 1
                continue
            sig = f"{item.origin}-{item.destination}-{item.price}"
            if sig not in seen:
                seen.add(sig)
                yield item

    async def _search_provider(self, provider: Provider, params: SearchParams) -> list[FlightOffer]:
        await self._rate_limiter.acquire(provider.name)
        return await provider.search_flights(params)

    async def _search_transport_provider(
        self, provider: Provider, params: SearchParams
    ) -> list[TransportOption]:
        await self._rate_limiter.acquire(provider.name)
        return await provider.search_transport(params)

    async def close(self) -> None:
        for provider in self._providers:
            await provider.close()
