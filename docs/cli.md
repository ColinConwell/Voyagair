# CLI Reference

Voyagair provides a command-line interface via the `voyagair` command.

## `voyagair search`

Search for flights between airports.

```bash
voyagair search ORIGINS DESTINATIONS DATES [OPTIONS]
```

**Arguments:**

- `ORIGINS` -- Origin airport(s), comma-separated (e.g. `CPT,JNB`)
- `DESTINATIONS` -- Destination airport(s), comma-separated (e.g. `JFK,EWR`)
- `DATES` -- Departure date(s), comma-separated (`YYYY-MM-DD`)

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--adults`, `-a` | 1 | Number of passengers |
| `--cabin`, `-c` | economy | Cabin class: economy, premium_economy, business, first |
| `--max-price`, `-p` | None | Maximum price filter |
| `--max-stops`, `-s` | None | Maximum number of stops |
| `--sort` | price | Sort by: price, duration, departure, stops |
| `--limit`, `-l` | 20 | Maximum results to display |
| `--currency` | USD | Currency code |
| `--providers` | None | Comma-separated provider names |

**Example:**

```bash
voyagair search CPT JFK 2026-04-15 --max-stops 1 --sort price
```

## `voyagair plan`

Plan multi-stop trips with route optimization and conflict-zone avoidance.

```bash
voyagair plan ORIGIN DESTINATION [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--waypoints`, `-w` | None | Comma-separated intermediate airports |
| `--avoid` | None | Conflict zones to avoid: `middle_east`, `ukraine` |
| `--max-stops`, `-s` | 3 | Max intermediate stops for route finding |
| `--suggest-from` | None | Compare airports as departure points |

**Examples:**

```bash
# Find routes avoiding the Middle East
voyagair plan CPT JFK --avoid middle_east

# Optimize multi-stop trip ordering
voyagair plan CPT JFK --waypoints WDH,VFA,JNB

# Compare departure airports
voyagair plan CPT JFK --avoid middle_east --suggest-from CPT,JNB,WDH,VFA
```

## `voyagair airports`

Browse and search the airport database.

```bash
voyagair airports [QUERY] [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--country`, `-c` | None | Filter by ISO country code (e.g. `ZA`, `US`) |
| `--limit`, `-l` | 20 | Maximum results |

**Examples:**

```bash
voyagair airports JFK
voyagair airports "cape town"
voyagair airports --country ZA
```

## `voyagair explore`

AI-assisted interactive travel planning. Requires an LLM API key.

```bash
voyagair explore [PROMPT] [OPTIONS]
```

If `PROMPT` is omitted, starts an interactive conversation.

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--model`, `-m` | gpt-5.4 | LLM model |
| `--provider` | openai | LLM provider: openai, anthropic, ollama |

**Example:**

```bash
voyagair explore "I need to fly from Cape Town to New York avoiding the Middle East"
```

## `voyagair serve`

Start the FastAPI API server.

```bash
voyagair serve [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host`, `-h` | 0.0.0.0 | Bind host |
| `--port`, `-p` | 8000 | Bind port |
| `--reload/--no-reload` | True | Auto-reload on changes |
