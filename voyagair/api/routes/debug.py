"""Backend debug/introspection endpoints."""

from __future__ import annotations

import logging
import os
import sys
import time

from fastapi import APIRouter
from pydantic import BaseModel

from voyagair.core.config import get_config

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.time()


class ProviderStatus(BaseModel):
    name: str
    configured: bool
    enabled: bool


class DebugInfo(BaseModel):
    python_version: str
    uptime_seconds: float
    env: dict[str, str]
    providers: list[ProviderStatus]
    llm: dict[str, str]
    cache: dict[str, str | int]
    data_dir: str
    recent_logs: list[str]


_log_buffer: list[str] = []
_MAX_LOG_BUFFER = 200


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        entry = self.format(record)
        _log_buffer.append(entry)
        if len(_log_buffer) > _MAX_LOG_BUFFER:
            _log_buffer.pop(0)


_handler = _BufferHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.getLogger("voyagair").addHandler(_handler)


@router.get("/info")
async def debug_info() -> DebugInfo:
    config = get_config()

    providers = [
        ProviderStatus(name="amadeus", configured=config.amadeus.is_configured(), enabled=config.amadeus.enabled),
        ProviderStatus(name="kiwi", configured=config.kiwi.is_configured(), enabled=config.kiwi.enabled),
        ProviderStatus(name="rome2rio", configured=config.rome2rio.is_configured(), enabled=config.rome2rio.enabled),
        ProviderStatus(name="google_flights", configured=config.google_flights.is_configured(), enabled=config.google_flights.enabled),
        ProviderStatus(name="serpapi", configured=config.serpapi.is_configured(), enabled=config.serpapi.enabled),
    ]

    env_keys = [
        "AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET", "KIWI_API_KEY",
        "ROME2RIO_API_KEY", "SERPAPI_KEY", "LLM_PROVIDER", "LLM_MODEL",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "VOYAGAIR_CACHE_DIR",
    ]
    env_status = {}
    for key in env_keys:
        val = os.getenv(key, "")
        if val:
            env_status[key] = f"***{val[-4:]}" if len(val) > 4 else "set"
        else:
            env_status[key] = "not set"

    return DebugInfo(
        python_version=sys.version.split()[0],
        uptime_seconds=round(time.time() - _start_time, 1),
        env=env_status,
        providers=providers,
        llm={"provider": config.llm.provider, "model": config.llm.model, "api_key": "set" if config.llm.api_key else "not set"},
        cache={"directory": config.cache.directory, "ttl_seconds": config.cache.ttl_seconds, "max_size_mb": config.cache.max_size_mb},
        data_dir=config.data_dir,
        recent_logs=list(_log_buffer[-50:]),
    )


@router.get("/logs")
async def recent_logs(limit: int = 50) -> dict:
    return {"logs": list(_log_buffer[-limit:]), "total": len(_log_buffer)}


@router.post("/logs/clear")
async def clear_logs() -> dict:
    _log_buffer.clear()
    return {"cleared": True}
