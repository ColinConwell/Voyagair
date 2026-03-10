"""Voyage API endpoints: CRUD, search, summary streaming, report, and config parsing."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel

from voyagair.core.config import get_config
from voyagair.core.search.orchestrator import SearchOrchestrator
from voyagair.core.voyage.models import VoyageConfig, VoyageResults
from voyagair.core.voyage.search import VoyageSearchOrchestrator
from voyagair.core.voyage.store import get_voyage_store
from voyagair.core.voyage.summary_agent import generate_summary, stream_summary
from voyagair.core.voyage.travel_agent import TravelAgentMCP

logger = logging.getLogger(__name__)

router = APIRouter()


class VoyageCreateResponse(BaseModel):
    id: str
    name: str


class VoyageSearchResponse(BaseModel):
    voyage_id: str
    flight_count: int
    transport_count: int
    search_duration_seconds: float
    results: VoyageResults


class ReportRequest(BaseModel):
    config: VoyageConfig | None = None
    results: VoyageResults | None = None
    format: Literal["html", "md", "pdf"] = "html"


class ParseConfigRequest(BaseModel):
    content: str
    format: Literal["yaml", "json", "markdown", "auto"] = "auto"


@router.post("/new")
async def create_voyage(config: VoyageConfig) -> VoyageCreateResponse:
    store = get_voyage_store()
    voyage_id = store.save(config)
    return VoyageCreateResponse(id=voyage_id, name=config.name)


@router.get("/list")
async def list_voyages():
    store = get_voyage_store()
    return {"voyages": store.list()}


@router.get("/{voyage_id}")
async def get_voyage(voyage_id: str):
    store = get_voyage_store()
    config = store.load(voyage_id)
    if config is None:
        return {"error": f"Voyage {voyage_id} not found"}
    return config.model_dump()


@router.delete("/{voyage_id}")
async def delete_voyage(voyage_id: str):
    store = get_voyage_store()
    deleted = store.delete(voyage_id)
    return {"deleted": deleted}


@router.post("/{voyage_id}/search")
async def search_voyage(voyage_id: str) -> VoyageSearchResponse:
    store = get_voyage_store()
    config = store.load(voyage_id)
    if config is None:
        return VoyageSearchResponse(
            voyage_id=voyage_id,
            flight_count=0,
            transport_count=0,
            search_duration_seconds=0,
            results=VoyageResults(voyage_id=voyage_id),
        )

    app_config = get_config()
    search_orch = VoyageSearchOrchestrator(config=app_config)
    try:
        results = await search_orch.search(config)
    finally:
        await search_orch.close()

    if config.travel_agent.enabled:
        try:
            ta = TravelAgentMCP(config.travel_agent)
            await ta.initialize()
            findings = await ta.gather_findings(config)
            results.travel_agent_findings = findings
            await ta.close()
        except Exception as e:
            logger.error("Travel agent failed: %s", e)
            results.travel_agent_findings = {"error": str(e)}

    try:
        results.agent_summary = await generate_summary(config, results)
    except Exception as e:
        logger.error("Summary generation failed: %s", e)

    store.save(config)

    return VoyageSearchResponse(
        voyage_id=config.id,
        flight_count=len(results.flight_options),
        transport_count=len(results.transport_options),
        search_duration_seconds=results.search_duration_seconds,
        results=results,
    )


@router.post("/search-inline")
async def search_voyage_inline(config: VoyageConfig) -> VoyageSearchResponse:
    """Search without requiring a saved voyage -- accepts config directly."""
    store = get_voyage_store()
    store.save(config)

    app_config = get_config()
    search_orch = VoyageSearchOrchestrator(config=app_config)
    try:
        results = await search_orch.search(config)
    finally:
        await search_orch.close()

    if config.travel_agent.enabled:
        try:
            ta = TravelAgentMCP(config.travel_agent)
            await ta.initialize()
            findings = await ta.gather_findings(config)
            results.travel_agent_findings = findings
            await ta.close()
        except Exception as e:
            logger.error("Travel agent failed: %s", e)

    try:
        results.agent_summary = await generate_summary(config, results)
    except Exception as e:
        logger.error("Summary generation failed: %s", e)

    return VoyageSearchResponse(
        voyage_id=config.id,
        flight_count=len(results.flight_options),
        transport_count=len(results.transport_options),
        search_duration_seconds=results.search_duration_seconds,
        results=results,
    )


@router.post("/parse-config")
async def parse_config_endpoint(req: ParseConfigRequest):
    """Parse a YAML/JSON/Markdown config string into a VoyageConfig."""
    from voyagair.core.voyage.config_parser import parse_config

    try:
        config = parse_config(req.content, fmt=req.format)
        return config.model_dump()
    except Exception as e:
        logger.error("Config parse failed: %s", e)
        return {"error": str(e)}


@router.post("/report")
async def generate_report_endpoint(req: ReportRequest):
    """Generate a report from config + optional results. Runs search if results not provided."""
    from voyagair.core.voyage.report import generate_report

    config = req.config
    results = req.results

    if config is None:
        return {"error": "config is required"}

    if results is None:
        app_config = get_config()
        search_orch = VoyageSearchOrchestrator(config=app_config)
        try:
            results = await search_orch.search(config)
        finally:
            await search_orch.close()

        try:
            results.agent_summary = await generate_summary(config, results)
        except Exception as e:
            logger.error("Summary generation failed: %s", e)

    refresh_url = f"/api/voyage/{config.id}/report"
    report = generate_report(config, results, fmt=req.format, refresh_url=refresh_url)

    if req.format == "pdf":
        return Response(content=report, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={config.id[:8]}-report.pdf"})
    if req.format == "md":
        return PlainTextResponse(report, media_type="text/markdown")
    return HTMLResponse(report)


@router.post("/{voyage_id}/report")
async def generate_saved_report(voyage_id: str, req: ReportRequest | None = None):
    """Generate a report for a saved voyage. Runs search automatically."""
    from voyagair.core.voyage.report import generate_report

    fmt = req.format if req else "html"

    store = get_voyage_store()
    config = store.load(voyage_id)
    if config is None:
        return {"error": f"Voyage {voyage_id} not found"}

    app_config = get_config()
    search_orch = VoyageSearchOrchestrator(config=app_config)
    try:
        results = await search_orch.search(config)
    finally:
        await search_orch.close()

    try:
        results.agent_summary = await generate_summary(config, results)
    except Exception as e:
        logger.error("Summary generation failed: %s", e)

    refresh_url = f"/api/voyage/{voyage_id}/report"
    report = generate_report(config, results, fmt=fmt, refresh_url=refresh_url)

    if fmt == "pdf":
        return Response(content=report, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={voyage_id[:8]}-report.pdf"})
    if fmt in ("md", "markdown"):
        return PlainTextResponse(report, media_type="text/markdown")
    return HTMLResponse(report)


@router.websocket("/ws/summary/{voyage_id}")
async def stream_voyage_summary(websocket: WebSocket, voyage_id: str):
    """WebSocket endpoint that streams the summary agent output token by token."""
    await websocket.accept()
    try:
        store = get_voyage_store()
        config = store.load(voyage_id)
        if config is None:
            await websocket.send_json({"type": "error", "message": "Voyage not found"})
            await websocket.close()
            return

        data = await websocket.receive_json()

        results = VoyageResults.model_validate(data) if data else VoyageResults(voyage_id=voyage_id)

        async for token in stream_summary(config, results):
            await websocket.send_json({"type": "token", "content": token})

        await websocket.send_json({"type": "complete"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Summary WebSocket error: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
