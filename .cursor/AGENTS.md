# Voyagair

Optimized, configurable path-of-least-resistance travel planner and flight finder.

## Project Structure

- `voyagair/` -- Python package (library, CLI, API server, AI agent)
  - `core/` -- Core library: data models, providers, graph, search, cache, rate limiter
    - `voyage/` -- Voyage configuration, location resolution, search orchestration, agents
  - `cli/` -- Typer CLI (`voyagair` command, including `voyage`, `app`, `search`, `plan`, `explore` subcommands)
  - `api/` -- FastAPI backend with REST, WebSocket, AI agent, debug, report, and config-parse endpoints
  - `app/` -- Vanilla HTML/CSS/JS web app (served at `/app`)
- `frontend/` -- Vite + TypeScript web UI with Leaflet map
  - `src/panels/` -- Voyage config, results, summary, debug panels
  - `src/components/` -- Reusable UI components (location autocomplete)
- `shared/` -- Shared resources (CSS variables, schema files, icons) used by both frontends
- `.cursor/rules/` -- Cursor project rules
- `.cursor/skills/` -- Cursor skills (travel-agent-mcp, flight-search-provider, voyagair-ui)
- `examples/` -- Sample config files (YAML/JSON/Markdown) for the voyage report pipeline
- `docs/` -- MkDocs documentation
- `data/` -- Static airport/route data (auto-downloaded on first run)

## Key Conventions

- Python 3.11+. Package at repo root (`voyagair/`), not under `src/`.
- Config loaded from `.env.local` (preferred) or `.env` via `python-dotenv`.
- All flight/transport providers implement `voyagair.core.providers.base.Provider`.
- Search orchestrator fans out to all configured providers concurrently.
- Pydantic v2 models throughout (`voyagair.core.search.models`).
- Async-first: all provider and search code is async.
- CLI built with Typer + Rich. API built with FastAPI + Uvicorn.
- AI agent uses LiteLLM for multi-provider LLM support (OpenAI, Anthropic, Gemini, local).
- Default LLM model: `gpt-5.4`. Configurable via `LLM_MODEL` env var.
- Rate limiting per provider via `pyrate-limiter`. Caching via `diskcache`.
- Route graph built with NetworkX from OurAirports + OpenFlights static data.
- Conflict-zone avoidance via great-circle bounding-box sampling.

## Common Commands

- `just install` -- Install the package in editable mode
- `just dev` -- Start API server + frontend dev server
- `just app` -- Launch the vanilla web app (opens browser)
- `just voyage` -- Manage voyage configurations (new, list, load, delete, parse, run)
- `just report <config>` -- Generate a voyage report from a config file
- `just cli` -- Run the CLI
- `just test` -- Run tests
- `just docs` -- Serve documentation locally

## Style

- No emojis in code or docs unless explicitly requested.
- Minimal comments -- only for non-obvious intent.
- Use `ruff` for formatting and linting.
- Dark theme is default; light theme via `[data-theme="light"]` on `<html>`.
- Theme preference persisted in localStorage (`voyagair-theme`).
