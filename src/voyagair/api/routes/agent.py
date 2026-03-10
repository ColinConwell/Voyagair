"""AI agent API endpoint for conversational travel planning."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_agents: dict[str, "TravelAgent"] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    model: str | None = None
    provider: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the AI travel agent."""
    from voyagair.api.agent.agent import TravelAgent

    if request.session_id not in _agents:
        _agents[request.session_id] = TravelAgent(
            model=request.model,
            provider=request.provider,
        )

    agent = _agents[request.session_id]
    response = await agent.chat(request.message)
    return ChatResponse(response=response, session_id=request.session_id)


@router.post("/reset")
async def reset_session(session_id: str = "default"):
    """Reset an agent conversation session."""
    if session_id in _agents:
        _agents[session_id].reset()
    return {"status": "ok", "session_id": session_id}
