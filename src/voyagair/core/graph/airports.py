"""Airport and route static data loader from OurAirports and OpenFlights datasets."""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import httpx

from voyagair.core.search.models import Airport

logger = logging.getLogger(__name__)

OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OPENFLIGHTS_ROUTES_URL = (
    "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"
)


class AirportDatabase:
    """In-memory airport database loaded from OurAirports CSV data."""

    def __init__(self) -> None:
        self._by_iata: dict[str, Airport] = {}
        self._by_icao: dict[str, Airport] = {}
        self._by_city: dict[str, list[Airport]] = {}
        self._by_country: dict[str, list[Airport]] = {}
        self._routes: list[tuple[str, str, str]] = []  # (src_iata, dst_iata, airline)

    @property
    def airports(self) -> dict[str, Airport]:
        return self._by_iata

    @property
    def routes(self) -> list[tuple[str, str, str]]:
        return self._routes

    def get(self, iata: str) -> Airport | None:
        return self._by_iata.get(iata.upper())

    def get_by_icao(self, icao: str) -> Airport | None:
        return self._by_icao.get(icao.upper())

    def search(self, query: str) -> list[Airport]:
        """Search airports by IATA, ICAO, name, or city (case-insensitive)."""
        q = query.upper().strip()
        results = []
        if q in self._by_iata:
            results.append(self._by_iata[q])
        if q in self._by_icao and self._by_icao[q] not in results:
            results.append(self._by_icao[q])
        ql = query.lower().strip()
        for airport in self._by_iata.values():
            if airport in results:
                continue
            if ql in airport.name.lower() or ql in airport.city.lower():
                results.append(airport)
        return results[:50]

    def get_by_city(self, city: str) -> list[Airport]:
        return self._by_city.get(city.lower(), [])

    def get_by_country(self, country_code: str) -> list[Airport]:
        return self._by_country.get(country_code.upper(), [])

    def get_routes_from(self, iata: str) -> list[tuple[str, str]]:
        """Get all direct routes from an airport as (destination_iata, airline)."""
        iata = iata.upper()
        return [(dst, airline) for src, dst, airline in self._routes if src == iata]

    def get_routes_to(self, iata: str) -> list[tuple[str, str]]:
        """Get all direct routes to an airport as (origin_iata, airline)."""
        iata = iata.upper()
        return [(src, airline) for src, dst, airline in self._routes if dst == iata]

    async def load(self, data_dir: str | Path | None = None) -> None:
        """Load airport and route data, downloading if not cached locally."""
        data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent.parent.parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        airports_file = data_dir / "airports.csv"
        routes_file = data_dir / "routes.dat"

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            if not airports_file.exists():
                logger.info("Downloading airport data from OurAirports...")
                resp = await client.get(OURAIRPORTS_URL)
                resp.raise_for_status()
                airports_file.write_text(resp.text, encoding="utf-8")

            if not routes_file.exists():
                logger.info("Downloading route data from OpenFlights...")
                resp = await client.get(OPENFLIGHTS_ROUTES_URL)
                resp.raise_for_status()
                routes_file.write_text(resp.text, encoding="utf-8")

        self._parse_airports(airports_file)
        self._parse_routes(routes_file)
        logger.info(
            "Loaded %d airports and %d routes",
            len(self._by_iata),
            len(self._routes),
        )

    def _parse_airports(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            iata = (row.get("iata_code") or "").strip()
            if not iata or iata == "0" or len(iata) != 3:
                continue
            atype = (row.get("type") or "").strip()
            if atype not in ("large_airport", "medium_airport", "small_airport"):
                continue
            try:
                lat = float(row.get("latitude_deg", 0))
                lon = float(row.get("longitude_deg", 0))
            except (ValueError, TypeError):
                lat, lon = 0.0, 0.0

            airport = Airport(
                iata=iata.upper(),
                icao=(row.get("ident") or "").strip().upper(),
                name=(row.get("name") or "").strip(),
                city=(row.get("municipality") or "").strip(),
                country=(row.get("iso_country") or "").strip(),
                country_code=(row.get("iso_country") or "").strip(),
                latitude=lat,
                longitude=lon,
                airport_type=atype,
            )
            self._by_iata[airport.iata] = airport
            if airport.icao:
                self._by_icao[airport.icao] = airport
            city_key = airport.city.lower()
            if city_key:
                self._by_city.setdefault(city_key, []).append(airport)
            if airport.country_code:
                self._by_country.setdefault(airport.country_code, []).append(airport)

    def _parse_routes(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        for line in text.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 5:
                continue
            airline = parts[0].strip()
            src = parts[2].strip()
            dst = parts[4].strip()
            if len(src) == 3 and len(dst) == 3 and src in self._by_iata and dst in self._by_iata:
                self._routes.append((src, dst, airline))


_db: AirportDatabase | None = None


async def get_airport_db(data_dir: str | Path | None = None) -> AirportDatabase:
    """Get or initialize the singleton airport database."""
    global _db
    if _db is None:
        _db = AirportDatabase()
        await _db.load(data_dir)
    return _db
