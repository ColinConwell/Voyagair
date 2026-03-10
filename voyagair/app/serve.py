"""Mount the vanilla app as FastAPI routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def app_index():
    index = TEMPLATES_DIR / "index.html"
    return HTMLResponse(index.read_text(encoding="utf-8"))


def mount_app_static(app):
    """Mount the vanilla app's static files on the given FastAPI app."""
    if STATIC_DIR.exists():
        app.mount(
            "/app/static",
            StaticFiles(directory=str(STATIC_DIR)),
            name="app-static",
        )
