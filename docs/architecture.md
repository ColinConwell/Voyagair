# Architecture

## Package Layout

```
voyagair/
  __init__.py
  core/
    config.py             # Config + .env.local loading
    cache.py              # Two-tier cache (LRU + diskcache)
    rate_limiter.py       # Per-provider rate limiting
    providers/
      base.py             # Abstract Provider interface
      google_flights.py   # Google Flights via faster-flights scraper
      amadeus_provider.py # Amadeus GDS official SDK
      kiwi.py             # Kiwi.com Tequila REST API
      rome2rio.py         # Rome2Rio multi-modal transport
    graph/
      airports.py         # Airport database (OurAirports + OpenFlights)
      route_graph.py      # NetworkX directed graph with conflict-zone filtering
      solver.py           # TSP solver (exact DP / simulated annealing)
    search/
      models.py           # Pydantic models (Airport, FlightOffer, SearchParams, etc.)
      filters.py          # Deduplication, filtering, sorting
      orchestrator.py     # Concurrent fan-out search across providers
  cli/
    app.py                # Typer CLI (search, plan, airports, explore, serve)
  api/
    app.py                # FastAPI application
    deps.py               # Shared dependencies (orchestrator singleton)
    routes/               # REST + WebSocket endpoints
    agent/
      agent.py            # LiteLLM-based conversational agent
      tools.py            # Tool definitions for function calling
```

## Data Flow

1. **User** issues a search (via CLI, REST API, or WebSocket)
2. **SearchOrchestrator** fans out to all configured providers concurrently
3. Each **Provider** makes its API/scraper call, respecting rate limits
4. Results are **deduplicated**, **filtered**, and **sorted**
5. **Cache** stores results for TTL-based reuse
6. For route planning, the **RouteGraph** (NetworkX) provides pathfinding with conflict-zone avoidance
7. The **RouteSolver** optimizes multi-stop ordering via TSP algorithms

## Conflict-Zone Avoidance

Routes are filtered by sampling points along great-circle arcs and checking if they fall within bounding boxes for known conflict zones. Currently defined zones:

- `middle_east`: (10N-42N, 25E-65E)
- `ukraine`: (44N-53N, 22E-41E)

## Provider System

All providers implement the `Provider` abstract base class:

- `search_flights(params) -> list[FlightOffer]`
- `search_transport(params) -> list[TransportOption]` (multimodal only)
- `is_configured() -> bool`
- `health_check() -> bool`

The orchestrator dynamically enables providers based on which API keys are configured.
