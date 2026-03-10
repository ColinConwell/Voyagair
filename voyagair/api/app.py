"""FastAPI application for Voyagair."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from voyagair.api.deps import set_orchestrator
from voyagair.api.routes import agent, airports, debug, plan, search, voyage, ws
from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db
from voyagair.core.search.orchestrator import SearchOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    await get_airport_db(config.data_dir)
    orchestrator = SearchOrchestrator.from_config(config)
    set_orchestrator(orchestrator)
    yield
    await orchestrator.close()


app = FastAPI(
    title="Voyagair API",
    description="Optimized, configurable path-of-least-resistance travel planner and flight finder.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(plan.router, prefix="/api/plan", tags=["plan"])
app.include_router(airports.router, prefix="/api/airports", tags=["airports"])
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(voyage.router, prefix="/api/voyage", tags=["voyage"])
app.include_router(debug.router, prefix="/api/debug", tags=["debug"])

from voyagair.app.serve import router as app_router, mount_app_static

app.include_router(app_router, prefix="/app", tags=["app"])
mount_app_static(app)

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def run():
    """Run the API server (for development)."""
    import uvicorn
    uvicorn.run("voyagair.api.app:app", host="0.0.0.0", port=8000, reload=True)
