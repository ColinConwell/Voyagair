"""WebSocket endpoint for streaming search results."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from voyagair.api.deps import get_orchestrator
from voyagair.core.search.models import CabinClass, SearchParams, SortKey

router = APIRouter()


@router.websocket("/search")
async def ws_search(websocket: WebSocket):
    """Stream flight search results as they arrive from each provider.

    Client sends a JSON message with search parameters, server streams
    results back one at a time as JSON messages.
    """
    await websocket.accept()

    try:
        raw = await websocket.receive_text()
        data = json.loads(raw)

        params = SearchParams(
            origins=data.get("origins", []),
            destinations=data.get("destinations", []),
            departure_dates=[date.fromisoformat(d) for d in data.get("departure_dates", [])],
            adults=data.get("adults", 1),
            cabin_class=CabinClass(data.get("cabin_class", "economy")),
            max_price=data.get("max_price"),
            max_stops=data.get("max_stops"),
            currency=data.get("currency", "USD"),
            sort_by=SortKey(data.get("sort_by", "price")),
            limit=data.get("limit", 50),
            providers=data.get("providers"),
        )

        orchestrator = get_orchestrator()
        count = 0

        async for offer in orchestrator.search_streaming(params):
            msg = {
                "type": "result",
                "data": offer.model_dump(mode="json"),
            }
            await websocket.send_text(json.dumps(msg, default=str))
            count += 1

        await websocket.send_text(json.dumps({
            "type": "complete",
            "count": count,
        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:
            pass
