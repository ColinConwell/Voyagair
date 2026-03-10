"""Persistence layer for Voyage configurations."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from voyagair.core.voyage.models import VoyageConfig

logger = logging.getLogger(__name__)

DEFAULT_VOYAGES_DIR = Path.home() / ".voyagair" / "voyages"


class VoyageStore:
    """Save, load, list, and delete VoyageConfig objects as JSON files."""

    def __init__(self, directory: str | Path | None = None):
        self._dir = Path(directory) if directory else DEFAULT_VOYAGES_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, voyage_id: str) -> Path:
        safe_id = voyage_id.replace("/", "_").replace("..", "_")
        return self._dir / f"{safe_id}.json"

    def save(self, config: VoyageConfig) -> str:
        config.updated_at = datetime.utcnow()
        path = self._path_for(config.id)
        path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved voyage %s to %s", config.id, path)
        return config.id

    def load(self, voyage_id: str) -> VoyageConfig | None:
        path = self._path_for(voyage_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return VoyageConfig.model_validate(data)
        except Exception:
            logger.exception("Failed to load voyage %s", voyage_id)
            return None

    def list(self) -> list[dict]:
        """Return summary info for all saved voyages, sorted by updated_at descending."""
        voyages: list[dict] = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                voyages.append({
                    "id": data.get("id", path.stem),
                    "name": data.get("name", "Untitled"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })
            except Exception:
                logger.warning("Skipping unreadable voyage file: %s", path)
        voyages.sort(key=lambda v: v.get("updated_at", ""), reverse=True)
        return voyages

    def delete(self, voyage_id: str) -> bool:
        path = self._path_for(voyage_id)
        if path.exists():
            path.unlink()
            logger.info("Deleted voyage %s", voyage_id)
            return True
        return False


_store: VoyageStore | None = None


def get_voyage_store(directory: str | Path | None = None) -> VoyageStore:
    global _store
    if _store is None:
        _store = VoyageStore(directory)
    return _store
