"""Config file parser: YAML, JSON, or Markdown -> VoyageConfig."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from voyagair.core.voyage.models import (
    CostBudget,
    LocationSpec,
    LocationType,
    TimeBudget,
    VoyageConfig,
)

logger = logging.getLogger(__name__)


def detect_format(content: str, filename: str | None = None) -> str:
    """Auto-detect config format from content or filename."""
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in (".yaml", ".yml"):
            return "yaml"
        if ext == ".json":
            return "json"
        if ext in (".md", ".markdown"):
            return "markdown"

    stripped = content.strip()
    if stripped.startswith("{"):
        return "json"
    if stripped.startswith("---") or re.match(r"^\w[\w\s]*:", stripped):
        return "yaml"
    return "markdown"


def parse_config(
    content: str,
    fmt: str = "auto",
    filename: str | None = None,
) -> VoyageConfig:
    """Parse a config string into VoyageConfig.

    Args:
        content: Raw config text (YAML, JSON, or Markdown).
        fmt: Format hint -- "yaml", "json", "markdown", or "auto".
        filename: Optional filename for format detection.

    Returns:
        Parsed VoyageConfig.
    """
    if fmt == "auto":
        fmt = detect_format(content, filename)

    if fmt == "json":
        return _parse_json(content)
    if fmt == "yaml":
        return _parse_yaml(content)
    if fmt == "markdown":
        return _parse_markdown(content)
    raise ValueError(f"Unsupported format: {fmt}")


def parse_config_file(path: str | Path) -> VoyageConfig:
    """Parse a config file from disk."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return parse_config(content, fmt="auto", filename=str(p))


def _parse_json(content: str) -> VoyageConfig:
    raw = json.loads(content)
    return _raw_to_config(raw)


def _parse_yaml(content: str) -> VoyageConfig:
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml is required for YAML config files. Install with: pip install pyyaml")
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise ValueError("YAML config must be a mapping at the top level")
    return _raw_to_config(raw)


def _parse_markdown(content: str) -> VoyageConfig:
    """Parse freeform Markdown into VoyageConfig via LLM or regex fallback."""
    try:
        return _parse_markdown_llm(content)
    except Exception as e:
        logger.warning("LLM-based markdown parsing failed (%s), falling back to regex", e)
        return _parse_markdown_regex(content)


def _parse_markdown_llm(content: str) -> VoyageConfig:
    """Use LiteLLM to extract travel config from freeform Markdown."""
    import litellm

    from voyagair.core.config import get_config

    llm_config = get_config().llm
    model_str = llm_config.model
    if llm_config.provider and llm_config.provider != "openai":
        model_str = f"{llm_config.provider}/{llm_config.model}"

    system = (
        "You are a travel config parser. Given freeform travel plans, extract structured "
        "JSON matching this schema:\n"
        "{\n"
        '  "name": "string",\n'
        '  "from": [{"type": "city|airport|country|region", "value": "string", "label": "string"}],\n'
        '  "to": [{"type": "city|airport|country|region", "value": "string", "label": "string"}],\n'
        '  "stops": [{"type": "city|airport", "value": "string", "label": "string"}],\n'
        '  "departure_date": "YYYY-MM-DD or null",\n'
        '  "flexible_dates": true/false,\n'
        '  "adults": number,\n'
        '  "cabin_class": "economy|premium_economy|business|first",\n'
        '  "budget": {"max_total": number, "currency": "USD"},\n'
        '  "max_stops": number or null,\n'
        '  "time_budget": {"total_days": number},\n'
        '  "avoid_airlines": ["carrier codes"],\n'
        '  "avoid_routing_regions": ["region names"],\n'
        '  "layover_regions": ["region names"],\n'
        '  "notes": "string"\n'
        "}\n"
        "Return ONLY valid JSON, no markdown fences."
    )

    import asyncio

    async def _call():
        resp = await litellm.acompletion(
            model=model_str,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return resp.choices[0].message.content

    raw_json = asyncio.get_event_loop().run_until_complete(_call())
    raw_json = raw_json.strip()
    if raw_json.startswith("```"):
        raw_json = re.sub(r"^```\w*\n?", "", raw_json)
        raw_json = re.sub(r"\n?```$", "", raw_json)

    raw = json.loads(raw_json)
    return _raw_to_config(raw)


def _parse_markdown_regex(content: str) -> VoyageConfig:
    """Best-effort extraction from Markdown without LLM."""
    config = VoyageConfig(name="Imported from Markdown")
    config.notes = content[:500]
    return config


def _location_spec(item: str | dict) -> LocationSpec:
    """Coerce a raw location entry into a LocationSpec."""
    if isinstance(item, str):
        val = item.strip().upper()
        if len(val) == 3 and val.isalpha():
            return LocationSpec(type=LocationType.AIRPORT, value=val, label=val)
        return LocationSpec(type=LocationType.CITY, value=item.strip(), label=item.strip())
    if isinstance(item, dict):
        loc_type = item.get("type", "city")
        try:
            lt = LocationType(loc_type)
        except ValueError:
            lt = LocationType.CITY
        return LocationSpec(
            type=lt,
            value=item.get("value", ""),
            label=item.get("label", item.get("value", "")),
        )
    raise ValueError(f"Cannot parse location: {item}")


def _raw_to_config(raw: dict) -> VoyageConfig:
    """Convert a friendly raw dict into a VoyageConfig, handling aliases."""
    starts = raw.get("starting_points") or raw.get("from") or []
    ends = raw.get("end_points") or raw.get("to") or []
    stops = raw.get("sites_along_the_way") or raw.get("stops") or raw.get("stops_along_the_way") or []

    if isinstance(starts, (str, dict)):
        starts = [starts]
    if isinstance(ends, (str, dict)):
        ends = [ends]
    if isinstance(stops, (str, dict)):
        stops = [stops]

    starting_points = [_location_spec(s) for s in starts]
    end_points = [_location_spec(e) for e in ends]
    sites = [_location_spec(s) for s in stops]

    budget_raw = raw.get("budget") or raw.get("cost_budget") or {}
    if isinstance(budget_raw, (int, float)):
        budget_raw = {"max_total": budget_raw}
    cost_budget = CostBudget(
        max_total=budget_raw.get("max_total"),
        max_per_leg=budget_raw.get("max_per_leg"),
        currency=budget_raw.get("currency", "USD"),
    )

    time_raw = raw.get("time_budget") or {}
    if isinstance(time_raw, (int, float)):
        time_raw = {"total_days": int(time_raw)}
    time_budget = TimeBudget(
        total_days=time_raw.get("total_days", 14),
        max_journey_hours=time_raw.get("max_journey_hours"),
    )

    cabin = raw.get("cabin_class", "economy")

    config = VoyageConfig(
        name=raw.get("name", "Untitled Voyage"),
        starting_points=starting_points,
        end_points=end_points,
        sites_along_the_way=sites,
        departure_date=raw.get("departure_date"),
        return_date=raw.get("return_date"),
        flexible_dates=bool(raw.get("flexible_dates", False)),
        adults=int(raw.get("adults", 1)),
        cabin_class=cabin,
        time_budget=time_budget,
        cost_budget=cost_budget,
        avoid_airlines=raw.get("avoid_airlines", []),
        avoid_routing_regions=raw.get("avoid_routing_regions", raw.get("avoid_regions", [])),
        layover_regions=raw.get("layover_regions", []),
        notes=raw.get("notes"),
    )

    if raw.get("max_stops") is not None:
        config.notes = (config.notes or "") + f"\nMax stops per leg: {raw['max_stops']}"

    return config
