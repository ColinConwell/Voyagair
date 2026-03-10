"""AI travel agent using LiteLLM for multi-provider LLM support."""

from __future__ import annotations

import json
import logging
from typing import Any

from voyagair.api.agent.tools import TOOL_DEFINITIONS, execute_tool
from voyagair.core.config import get_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Voyagair, an expert AI travel planning assistant. You help users find optimal flights, \
plan multi-stop trips, and navigate complex travel routing scenarios.

You have access to tools that let you:
- Search for flights between airports
- Look up airport information
- Find routes between cities (including avoiding conflict zones like the Middle East)
- Compare departure airports
- Optimize multi-stop trip ordering

When helping users:
- Always search for actual flight data before making recommendations
- Consider budget constraints, travel time preferences, and safety concerns
- Suggest alternative routes when direct flights are expensive or unavailable
- Provide clear, structured summaries of options
- When users mention avoiding conflict zones, use the find_routes tool with appropriate avoid_zones

For airport codes, use IATA codes (3 letters). If a user mentions a city name, look up the airport \
code first. Common Southern/East African airports: CPT (Cape Town), JNB (Johannesburg), \
WDH (Windhoek), VFA (Victoria Falls), NBO (Nairobi), ADD (Addis Ababa), \
DAR (Dar es Salaam), LUN (Lusaka).

Common US East Coast airports: JFK (New York JFK), EWR (Newark), IAD (Washington Dulles), \
BOS (Boston), PHL (Philadelphia), ATL (Atlanta).
"""


class TravelAgent:
    """Conversational AI agent backed by LiteLLM."""

    def __init__(self, model: str | None = None, provider: str | None = None):
        config = get_config()
        self._model = model or config.llm.model
        self._provider = provider or config.llm.provider
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        model_str = self._model
        if self._provider and self._provider != "openai":
            model_str = f"{self._provider}/{self._model}"
        self._model_str = model_str

    async def chat(self, user_message: str) -> str:
        """Send a message and get a response, handling tool calls."""
        try:
            import litellm
        except ImportError:
            return (
                "The AI agent requires litellm. Install with: `pip install litellm`\n\n"
                "You also need to set an LLM API key:\n"
                "  export OPENAI_API_KEY=your-key    (for OpenAI)\n"
                "  export ANTHROPIC_API_KEY=your-key  (for Anthropic)"
            )

        self._messages.append({"role": "user", "content": user_message})

        max_rounds = 5
        for _ in range(max_rounds):
            try:
                response = await litellm.acompletion(
                    model=self._model_str,
                    messages=self._messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.3,
                )
            except Exception as e:
                logger.error("LLM call failed: %s", e)
                error_msg = f"LLM call failed: {e}"
                self._messages.pop()
                return error_msg

            choice = response.choices[0]
            message = choice.message

            self._messages.append(message.model_dump())

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    fn = tool_call.function
                    try:
                        args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                        result = await execute_tool(fn.name, args)
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                continue

            return message.content or ""

        return "I reached the maximum number of tool call rounds. Please try a simpler query."

    def reset(self) -> None:
        """Clear conversation history."""
        self._messages = [{"role": "system", "content": SYSTEM_PROMPT}]
