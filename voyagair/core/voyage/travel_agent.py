"""Travel Agent with MCP integration for gathering supplemental travel information."""

from __future__ import annotations

import json
import logging
from typing import Any

from voyagair.core.config import get_config
from voyagair.core.voyage.models import MCPServerConfig, TravelAgentConfig, VoyageConfig

logger = logging.getLogger(__name__)

TRAVEL_AGENT_SYSTEM_PROMPT = """\
You are a Voyagair Travel Agent. You supplement programmatic flight search results \
with additional context gathered from external tools and data sources.

Your responsibilities:
- Use available tools to find supplemental travel information
- Look for alternative routes, hidden-city ticketing opportunities, or airline deals
- Gather destination information (visa requirements, weather, local tips)
- Find accommodation and ground transport options near airports
- Report your findings as structured data that can be merged with programmatic results

Always be factual and cite your sources when possible. Do not use emojis.
"""


class BuiltinToolRegistry:
    """Wraps the existing Voyagair agent tools as callable functions."""

    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}

    async def initialize(self) -> None:
        from voyagair.api.agent.tools import TOOL_DEFINITIONS, execute_tool
        self._execute = execute_tool
        for td in TOOL_DEFINITIONS:
            fn = td["function"]
            self._tools[fn["name"]] = td

    @property
    def tool_definitions(self) -> list[dict]:
        return list(self._tools.values())

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if not hasattr(self, "_execute"):
            await self.initialize()
        return await self._execute(name, arguments)


class MCPClient:
    """Placeholder client for connecting to external MCP servers.

    Downstream users can subclass this or replace it with a full MCP SDK client.
    """

    def __init__(self, server_config: MCPServerConfig):
        self.config = server_config
        self._connected = False

    async def connect(self) -> bool:
        if not self.config.url:
            logger.warning("MCP server %s has no URL configured", self.config.name)
            return False
        logger.info("Connecting to MCP server: %s at %s", self.config.name, self.config.url)
        self._connected = True
        return True

    async def list_tools(self) -> list[dict]:
        """List available tools on the MCP server."""
        if not self._connected:
            return []
        return [{"name": t, "server": self.config.name} for t in self.config.tools]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server. Placeholder -- returns a stub response."""
        if not self._connected:
            return json.dumps({"error": f"Not connected to {self.config.name}"})
        logger.info(
            "MCP tool call: %s/%s with args %s",
            self.config.name, tool_name, arguments,
        )
        return json.dumps({
            "status": "placeholder",
            "server": self.config.name,
            "tool": tool_name,
            "message": (
                f"MCP tool '{tool_name}' on server '{self.config.name}' "
                "is a placeholder. Implement the MCPClient.call_tool method "
                "or connect a real MCP SDK client."
            ),
        })

    async def disconnect(self) -> None:
        self._connected = False


class TravelAgentMCP:
    """Orchestrates builtin tools + external MCP servers for the Travel Agent."""

    def __init__(self, agent_config: TravelAgentConfig):
        self.agent_config = agent_config
        self._builtin = BuiltinToolRegistry()
        self._mcp_clients: list[MCPClient] = []

    async def initialize(self) -> None:
        if self.agent_config.use_builtin_tools:
            await self._builtin.initialize()

        for server_cfg in self.agent_config.mcp_servers:
            if not server_cfg.enabled:
                continue
            client = MCPClient(server_cfg)
            connected = await client.connect()
            if connected:
                self._mcp_clients.append(client)

    async def gather_findings(self, voyage: VoyageConfig) -> dict[str, Any]:
        """Run the travel agent to gather supplemental information.

        Uses the LLM with tool-calling to explore options beyond
        the programmatic search.
        """
        try:
            import litellm
        except ImportError:
            return {"error": "litellm not installed", "findings": []}

        llm_config = get_config().llm
        model = self.agent_config.model or llm_config.model
        provider = self.agent_config.provider or llm_config.provider
        model_str = model
        if provider and provider != "openai":
            model_str = f"{provider}/{model}"

        tools = []
        if self.agent_config.use_builtin_tools:
            tools.extend(self._builtin.tool_definitions)

        starts = ", ".join(f"{s.type.value}:{s.value}" for s in voyage.starting_points)
        ends = ", ".join(f"{e.type.value}:{e.value}" for e in voyage.end_points)
        sites = ", ".join(f"{s.type.value}:{s.value}" for s in voyage.sites_along_the_way)

        user_prompt = (
            f"Research travel options for a trip:\n"
            f"From: {starts}\n"
            f"To: {ends}\n"
        )
        if sites:
            user_prompt += f"Sites along the way: {sites}\n"
        if voyage.departure_date:
            user_prompt += f"Departure date: {voyage.departure_date}\n"
        if voyage.cost_budget.max_total:
            user_prompt += f"Budget: {voyage.cost_budget.currency} {voyage.cost_budget.max_total}\n"
        if self.agent_config.custom_instructions:
            user_prompt += f"\nAdditional instructions: {self.agent_config.custom_instructions}\n"

        user_prompt += "\nSearch for flights and routes, then provide a structured summary of your findings."

        system_prompt = TRAVEL_AGENT_SYSTEM_PROMPT
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        findings: list[dict] = []
        max_rounds = 5

        for _ in range(max_rounds):
            try:
                kwargs: dict[str, Any] = {
                    "model": model_str,
                    "messages": messages,
                    "temperature": 0.3,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = await litellm.acompletion(**kwargs)
            except Exception as e:
                logger.error("Travel agent LLM call failed: %s", e)
                return {"error": str(e), "findings": findings}

            choice = response.choices[0]
            message = choice.message
            messages.append(message.model_dump())

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    fn = tool_call.function
                    try:
                        args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                        result = await self._dispatch_tool(fn.name, args)
                        findings.append({
                            "tool": fn.name,
                            "args": args,
                            "result": json.loads(result) if isinstance(result, str) else result,
                        })
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                continue

            return {
                "summary": message.content or "",
                "findings": findings,
            }

        return {"summary": "Reached maximum tool call rounds.", "findings": findings}

    async def _dispatch_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self.agent_config.use_builtin_tools:
            try:
                return await self._builtin.call(name, arguments)
            except Exception:
                pass

        for client in self._mcp_clients:
            server_tools = await client.list_tools()
            if any(t["name"] == name for t in server_tools):
                return await client.call_tool(name, arguments)

        return json.dumps({"error": f"Tool '{name}' not found in any provider"})

    async def close(self) -> None:
        for client in self._mcp_clients:
            await client.disconnect()
