# Setup

## Prerequisites

- Python 3.11+
- Node.js 18+ (for the web frontend)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
# Clone the repo
git clone https://github.com/colinconwell/Voyagair.git
cd Voyagair

# Create a virtual environment and install
uv venv .venv --python 3.11
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Copy the example environment file and add your API keys:

```bash
cp .env.example .env.local
```

Voyagair loads configuration from `.env.local` (preferred) or `.env`. The config loader (`voyagair.core.config`) reads these automatically via `python-dotenv`.

## API Keys

The tool works with **zero API keys** using the Google Flights scraper and static airport/route data. API keys unlock richer data sources:

| Service | Env Variable(s) | Free Tier | Sign Up |
|---------|-----------------|-----------|---------|
| Amadeus | `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET` | 2,000 searches/month | [developers.amadeus.com](https://developers.amadeus.com) |
| Kiwi Tequila | `KIWI_API_KEY` | Free search | [tequila.kiwi.com](https://tequila.kiwi.com) |
| Rome2Rio | `ROME2RIO_API_KEY` | 100,000 searches/month | [rome2rio.com](https://www.rome2rio.com/documentation/search) |
| SerpAPI | `SERPAPI_KEY` | 250 searches/month | [serpapi.com](https://serpapi.com) |

For the AI agent, set one or more LLM provider keys:

| Provider | Env Variable |
|----------|-------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google | `GEMINI_API_KEY` |

The default model is `gpt-5.4`. Change it with `LLM_MODEL` and `LLM_PROVIDER`.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev      # Dev server on http://localhost:3000
```

The frontend proxies API requests to `http://localhost:8000`, so start the API server too:

```bash
voyagair serve   # Starts FastAPI on http://localhost:8000
```

## Docker

```bash
cp .env.example .env.local
docker compose up
```

This builds the backend and frontend into a single image and serves everything on port 8000.

## Static Data

On first run, Voyagair downloads two datasets into `data/`:

- **airports.csv** -- 8,400+ airports from [OurAirports](https://ourairports.com/data/)
- **routes.dat** -- 67,000+ routes from [OpenFlights](https://openflights.org/data.html)

These are cached locally and reused on subsequent runs.
