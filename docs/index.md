# Voyagair

Optimized, configurable path-of-least-resistance travel planner and flight finder.

Voyagair is a Python library, CLI tool, and web application for multi-stop trip planning and flight search. It aggregates results from multiple providers, supports conflict-zone avoidance routing, and includes an AI agent for conversational travel planning.

## Components

| Component | Description |
|-----------|-------------|
| **Core Library** | Provider-agnostic flight search, route graph, TSP solver, caching, rate limiting |
| **CLI** | `voyagair search`, `plan`, `airports`, `explore`, `serve` |
| **API Server** | FastAPI with REST, WebSocket streaming, and AI agent endpoints |
| **Web UI** | Vite + TypeScript frontend with Leaflet map and real-time results |

## Getting Started

See the [Setup Guide](setup.md) for installation and configuration instructions.
