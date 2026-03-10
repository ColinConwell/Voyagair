# API Reference

The Voyagair API server runs on FastAPI. Start it with `voyagair serve` or `uvicorn voyagair.api.app:app`.

Interactive API docs are available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

## Endpoints

### Health Check

```
GET /api/health
```

Returns `{"status": "ok", "version": "0.1.0"}`.

### Flight Search

```
POST /api/search/flights
```

**Request body:**

```json
{
  "origins": ["CPT"],
  "destinations": ["JFK"],
  "departure_dates": ["2026-04-15"],
  "adults": 1,
  "cabin_class": "economy",
  "max_price": null,
  "max_stops": null,
  "sort_by": "price",
  "limit": 50
}
```

```
GET /api/search/flights?origin=CPT&destination=JFK&date=2026-04-15
```

### Route Planning

```
POST /api/plan/optimize
```

Find optimal waypoint ordering:

```json
{
  "origin": "CPT",
  "destination": "JFK",
  "waypoints": ["WDH", "VFA", "JNB"],
  "avoid_zones": ["middle_east"]
}
```

```
POST /api/plan/routes
```

Find routes with conflict-zone avoidance.

```
POST /api/plan/suggest-departures
```

Compare departure airports:

```json
{
  "airports": ["CPT", "JNB", "WDH", "VFA"],
  "destination": "JFK",
  "avoid_zones": ["middle_east"]
}
```

### Airports

```
GET /api/airports/search?q=cape+town
GET /api/airports/{iata}
GET /api/airports/{iata}/routes?direction=from
GET /api/airports/country/{country_code}
```

### AI Agent

```
POST /api/agent/chat
```

```json
{
  "message": "Find me flights from Cape Town to New York",
  "session_id": "default"
}
```

```
POST /api/agent/reset?session_id=default
```

### WebSocket (Streaming Search)

```
WS /api/ws/search
```

Send a JSON search params message after connecting. Results stream back as individual JSON messages:

```json
{"type": "result", "data": {...}}
{"type": "complete", "count": 15}
```

## Architecture

```
Client -> FastAPI (REST / WebSocket)
            -> SearchOrchestrator
                -> [Google Flights, Amadeus, Kiwi, Rome2Rio]
            -> RouteGraph + RouteSolver
            -> AI Agent (LiteLLM -> tools -> core library)
```
