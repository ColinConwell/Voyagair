# Voyagair

Optimized, configurable path-of-least-resistance travel planner and flight finder.

Voyagair is a Python library, CLI tool, and web application for multi-stop trip planning and flight search. It aggregates results from multiple providers (Google Flights, Amadeus GDS, Kiwi.com Tequila, Rome2Rio), supports conflict-zone avoidance routing, and includes an AI agent for conversational travel planning.

## Quick Start

```bash
# Install
pip install -e .

# Search for flights
voyagair search CPT JFK 2026-04-15

# Compare departure airports (avoiding Middle East conflict zones)
voyagair plan CPT JFK --avoid middle_east --suggest-from CPT,JNB,WDH,VFA

# Find routes with conflict-zone avoidance
voyagair plan CPT JFK --avoid middle_east

# Optimize multi-stop trip ordering
voyagair plan CPT JFK --waypoints WDH,VFA,JNB --avoid middle_east

# Browse airports
voyagair airports --country ZA
voyagair airports "cape town"

# AI-assisted exploration (requires LLM API key)
voyagair explore "I need to get from Cape Town to New York, avoiding Middle East flight paths"

# Start the API server
voyagair serve
```

## API Keys

The tool works with **zero API keys** using the Google Flights scraper and static airport/route data. API keys unlock richer data sources:

| Service | Env Variable | Free Tier |
|---------|-------------|-----------|
| Amadeus | `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET` | 2,000 searches/month |
| Kiwi Tequila | `KIWI_API_KEY` | Free search |
| Rome2Rio | `ROME2RIO_API_KEY` | 100,000 searches/month |
| LLM (AI agent) | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Varies |

Copy `.env.example` to `.env` and fill in your keys.

## Architecture

```
voyagair/
  src/voyagair/
    core/               # Library core
      providers/        # Flight data providers (Google Flights, Amadeus, Kiwi, Rome2Rio)
      graph/            # Airport database, route graph (NetworkX), TSP solver
      search/           # Search orchestrator, Pydantic models, filters
      cache.py          # Two-tier cache (in-memory LRU + diskcache)
      rate_limiter.py   # Per-provider rate limiting (pyrate-limiter)
    cli/                # Typer CLI (search, plan, airports, explore, serve)
    api/                # FastAPI backend (REST + WebSocket + AI agent)
  frontend/             # Vite + TypeScript web UI with Leaflet map
```

## Web UI

```bash
cd frontend && npm install && npm run dev   # Dev server on :3000
voyagair serve                               # API server on :8000
```

## Docker

```bash
cp .env.example .env  # Add your API keys
docker compose up
```
