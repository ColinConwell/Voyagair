"""Shared dependencies for API routes."""

from __future__ import annotations

from voyagair.core.search.orchestrator import SearchOrchestrator

_orchestrator: SearchOrchestrator | None = None


def get_orchestrator() -> SearchOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SearchOrchestrator.from_config()
    return _orchestrator


def set_orchestrator(orchestrator: SearchOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator
