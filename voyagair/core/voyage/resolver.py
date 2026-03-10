"""Resolve LocationSpec objects to concrete IATA airport codes."""

from __future__ import annotations

import logging

from voyagair.core.graph.airports import AirportDatabase
from voyagair.core.voyage.models import LocationSpec, LocationType

logger = logging.getLogger(__name__)

REGION_MAP: dict[str, list[str]] = {
    "Europe": [
        "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ", "DK",
        "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "XK", "LV",
        "LI", "LT", "LU", "MT", "MD", "ME", "NL", "MK", "NO", "PL", "PT",
        "RO", "RS", "SK", "SI", "ES", "SE", "CH", "UA", "GB",
    ],
    "Western Europe": [
        "AT", "BE", "FR", "DE", "IE", "LI", "LU", "MC", "NL", "CH", "GB",
    ],
    "Eastern Europe": [
        "BY", "BG", "CZ", "HU", "MD", "PL", "RO", "SK", "UA",
    ],
    "Scandinavia": ["DK", "FI", "IS", "NO", "SE"],
    "North America": ["US", "CA", "MX"],
    "Central America": ["BZ", "CR", "SV", "GT", "HN", "NI", "PA"],
    "Caribbean": [
        "AG", "BS", "BB", "CU", "DM", "DO", "GD", "HT", "JM", "KN", "LC",
        "VC", "TT", "PR", "VI",
    ],
    "South America": [
        "AR", "BO", "BR", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE",
    ],
    "East Africa": ["BI", "KM", "DJ", "ER", "ET", "KE", "MG", "MW", "MU", "MZ", "RW", "SC", "SO", "SS", "TZ", "UG"],
    "Southern Africa": ["BW", "LS", "NA", "ZA", "SZ", "ZM", "ZW"],
    "West Africa": [
        "BJ", "BF", "CV", "CI", "GM", "GH", "GN", "GW", "LR", "ML", "MR",
        "NE", "NG", "SN", "SL", "TG",
    ],
    "North Africa": ["DZ", "EG", "LY", "MA", "SD", "TN"],
    "Middle East": [
        "BH", "IQ", "IR", "IL", "JO", "KW", "LB", "OM", "PS", "QA", "SA",
        "SY", "AE", "YE",
    ],
    "Central Asia": ["KZ", "KG", "TJ", "TM", "UZ"],
    "South Asia": ["AF", "BD", "BT", "IN", "MV", "NP", "PK", "LK"],
    "Southeast Asia": ["BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN"],
    "East Asia": ["CN", "HK", "JP", "KP", "KR", "MO", "MN", "TW"],
    "Oceania": ["AU", "FJ", "KI", "MH", "FM", "NR", "NZ", "PW", "PG", "WS", "SB", "TO", "TV", "VU"],
}


async def resolve_location(
    spec: LocationSpec, db: AirportDatabase, *, major_only: bool = True
) -> list[str]:
    """Resolve a LocationSpec to a list of IATA codes.

    For region/country, returns only large/medium airports by default
    to keep search scope manageable.
    """
    if spec.type == LocationType.AIRPORT:
        code = spec.value.strip().upper()
        airport = db.get(code)
        if airport:
            return [code]
        results = db.search(spec.value)
        return [results[0].iata] if results else []

    if spec.type == LocationType.CITY:
        airports = db.get_by_city(spec.value.strip())
        if not airports:
            results = db.search(spec.value)
            airports = results[:5]
        if major_only:
            airports = [a for a in airports if a.airport_type in ("large_airport", "medium_airport")] or airports
        return [a.iata for a in airports]

    if spec.type == LocationType.COUNTRY:
        code = spec.value.strip().upper()
        airports = db.get_by_country(code)
        if major_only:
            airports = [a for a in airports if a.airport_type == "large_airport"] or airports[:10]
        return [a.iata for a in airports]

    if spec.type == LocationType.REGION:
        region_name = spec.value.strip()
        country_codes = REGION_MAP.get(region_name, [])
        if not country_codes:
            for key, codes in REGION_MAP.items():
                if key.lower() == region_name.lower():
                    country_codes = codes
                    break
        if not country_codes:
            logger.warning("Unknown region: %s", region_name)
            return []
        iatas: list[str] = []
        for cc in country_codes:
            airports = db.get_by_country(cc)
            large = [a for a in airports if a.airport_type == "large_airport"]
            iatas.extend(a.iata for a in (large or airports[:3]))
        return iatas

    return []


async def resolve_locations(
    specs: list[LocationSpec], db: AirportDatabase
) -> list[str]:
    """Resolve multiple LocationSpecs to a flat, deduplicated list of IATA codes."""
    all_codes: list[str] = []
    seen: set[str] = set()
    for spec in specs:
        codes = await resolve_location(spec, db)
        spec.resolved_airports = codes
        for code in codes:
            if code not in seen:
                seen.add(code)
                all_codes.append(code)
    return all_codes
