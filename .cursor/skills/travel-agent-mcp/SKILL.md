# Travel Agent MCP Development

Use this skill when working on:
- The Travel Agent (`voyagair/core/voyage/travel_agent.py`)
- MCP tool integration for flight lookups
- Adding new MCP server connectors
- Configuring external travel data providers

## Architecture

The Travel Agent system has three layers:
1. **BuiltinToolRegistry** - wraps existing Voyagair search providers as callable tools
2. **MCPClient** - connects to external MCP servers for supplemental data
3. **TravelAgentMCP** - orchestrates both, using LiteLLM for AI-driven tool selection

## Key Files
- `voyagair/core/voyage/travel_agent.py` - Main Travel Agent implementation
- `voyagair/core/voyage/models.py` - TravelAgentConfig, MCPServerConfig models
- `voyagair/core/search/orchestrator.py` - Underlying search orchestrator
- `voyagair/core/providers/` - Flight search provider implementations
- `voyagair/api/routes/voyage.py` - API endpoints that invoke the Travel Agent

## Adding a New MCP Tool

1. Define the tool in the MCPServerConfig:
   ```python
   MCPServerConfig(
       name="my-tool",
       url="http://localhost:3001",
       tools=["search_flights", "get_prices"],
       enabled=True,
   )
   ```

2. The TravelAgentMCP will discover tools from the server at initialization.

3. Built-in tools are registered in BuiltinToolRegistry and wrap:
   - `search_flights` - Fan-out search across all configured providers
   - `search_airport` - Airport information lookup
   - `find_routes` - Route graph pathfinding

## Testing
- Run `just dev` to start the backend
- Use the Voyage config panel to enable Travel Agent
- Check API at POST /api/voyage/search-inline with travel_agent.enabled=true
