"""Per-provider rate limiting using pyrate-limiter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyrate_limiter import Duration, Limiter, Rate

logger = logging.getLogger(__name__)


class ProviderRateLimiter:
    """Rate limiter that manages per-provider request budgets."""

    def __init__(self) -> None:
        self._limiters: dict[str, Limiter] = {}

    def register(self, provider_name: str, max_calls: int, period_seconds: float) -> None:
        """Register a rate limit for a provider."""
        rate = Rate(max_calls, Duration.SECOND * int(period_seconds))
        self._limiters[provider_name] = Limiter(rate)
        logger.debug(
            "Registered rate limit for %s: %d calls per %ss",
            provider_name, max_calls, period_seconds,
        )

    async def acquire(self, provider_name: str) -> None:
        """Wait until a request slot is available for the given provider."""
        limiter = self._limiters.get(provider_name)
        if limiter is None:
            return
        while True:
            try:
                limiter.try_acquire(provider_name)
                return
            except Exception:
                await asyncio.sleep(0.1)

    def is_registered(self, provider_name: str) -> bool:
        return provider_name in self._limiters


_rate_limiter: ProviderRateLimiter | None = None


def get_rate_limiter() -> ProviderRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = ProviderRateLimiter()
    return _rate_limiter
