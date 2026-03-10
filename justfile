# Voyagair -- path-of-least-resistance travel planner

set dotenv-filename := ".env.local"

# ─── Setup ──────────────────────────────────────────────

# Create virtual environment and install package
install:
    uv venv .venv --python 3.11
    VIRTUAL_ENV=.venv uv pip install -e ".[dev]"
    cd frontend && npm install

# Install package only (no frontend)
install-py:
    VIRTUAL_ENV=.venv uv pip install -e ".[dev]"

# Install frontend only
install-fe:
    cd frontend && npm install

# ─── Development ────────────────────────────────────────

# Start API server (port 8000) + frontend dev server (port 3000)
dev:
    @echo "Starting API server and frontend dev server..."
    @just api &
    @just fe

# Start API server with auto-reload
api:
    .venv/bin/voyagair serve --port 8000

# Start frontend dev server
fe:
    cd frontend && npm run dev

# Build frontend for production
build-fe:
    cd frontend && npm run build

# ─── CLI ────────────────────────────────────────────────

# Run the Voyagair CLI (pass args after --)
cli *ARGS:
    .venv/bin/voyagair {{ARGS}}

# Search flights (e.g. just search CPT JFK 2026-04-15)
search ORIGINS DESTINATIONS DATES *OPTS:
    .venv/bin/voyagair search {{ORIGINS}} {{DESTINATIONS}} {{DATES}} {{OPTS}}

# Plan a trip with route optimization
plan ORIGIN DESTINATION *OPTS:
    .venv/bin/voyagair plan {{ORIGIN}} {{DESTINATION}} {{OPTS}}

# Browse airports
airports *ARGS:
    .venv/bin/voyagair airports {{ARGS}}

# AI-assisted travel exploration
explore *ARGS:
    .venv/bin/voyagair explore {{ARGS}}

# Launch the vanilla web app (opens browser)
app *ARGS:
    .venv/bin/voyagair app {{ARGS}}

# Manage voyages
voyage *ARGS:
    .venv/bin/voyagair voyage {{ARGS}}

# ─── Testing & Quality ─────────────────────────────────

# Run tests
test *ARGS:
    .venv/bin/pytest {{ARGS}}

# Lint and format
lint:
    .venv/bin/ruff check voyagair/
    .venv/bin/ruff format --check voyagair/

# Auto-fix lint issues
fix:
    .venv/bin/ruff check --fix voyagair/
    .venv/bin/ruff format voyagair/

# Type check
typecheck:
    .venv/bin/mypy voyagair/

# ─── Documentation ──────────────────────────────────────

# Serve docs locally
docs:
    .venv/bin/mkdocs serve

# Build docs
docs-build:
    .venv/bin/mkdocs build

# ─── Docker ─────────────────────────────────────────────

# Build and run with Docker Compose
docker-up:
    docker compose up --build

# Stop Docker Compose services
docker-down:
    docker compose down

# ─── Data ───────────────────────────────────────────────

# Download airport and route data
data:
    .venv/bin/python -c "import asyncio; from voyagair.core.graph.airports import get_airport_db; asyncio.run(get_airport_db())"

# Clear cached search results
clean-cache:
    rm -rf .voyagair_cache

# Clean all generated files
clean:
    rm -rf .voyagair_cache .venv frontend/dist frontend/node_modules data/airports.csv data/routes.dat
