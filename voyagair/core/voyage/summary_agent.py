"""Summary Agent: generates narrative summaries of voyage search results."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from voyagair.core.config import get_config
from voyagair.core.voyage.models import VoyageConfig, VoyageResults

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """\
You are the Voyagair Summary Agent. Your role is to provide clear, helpful narrative \
summaries of travel search results for a user planning a trip.

Given a voyage configuration and search results, you should:
- Highlight the best options by price, duration, and convenience
- Note trade-offs between cheaper vs faster options
- Call out nonstop flights when available
- Mention any notable carriers or routing patterns
- If waypoints/sites along the way were specified, comment on how the multi-stop \
  itinerary compares to direct routing
- If a travel agent was used, integrate its findings into your narrative
- Keep the summary concise but informative (aim for 3-6 paragraphs)
- Use markdown formatting for readability
- Do not use emojis

Format your response as a well-structured travel briefing.
"""


def _build_results_context(config: VoyageConfig, results: VoyageResults) -> str:
    """Serialize the voyage config and results into a prompt context string."""
    starts = [f"{s.type.value}: {s.value}" for s in config.starting_points]
    ends = [f"{e.type.value}: {e.value}" for e in config.end_points]
    sites = [f"{s.type.value}: {s.value}" for s in config.sites_along_the_way]

    flights_summary = []
    for i, f in enumerate(results.flight_options[:20], 1):
        flights_summary.append({
            "rank": i,
            "route": f"{f.origin} -> {f.destination}",
            "price": f"{f.currency} {f.price:,.0f}",
            "duration_min": f.total_duration_minutes,
            "stops": f.num_stops,
            "carriers": list({leg.carrier for leg in f.legs if leg.carrier}),
            "provider": f.provider,
        })

    transport_summary = []
    for t in results.transport_options[:10]:
        transport_summary.append({
            "route": f"{t.origin} -> {t.destination}",
            "mode": t.mode.value,
            "carrier": t.carrier,
            "price_range": f"{t.currency} {t.price_min or '?'}-{t.price_max or '?'}",
        })

    context = {
        "voyage_name": config.name,
        "starting_points": starts,
        "end_points": ends,
        "sites_along_the_way": sites or None,
        "departure_date": config.departure_date,
        "adults": config.adults,
        "cabin_class": config.cabin_class.value,
        "time_budget": {
            "total_days": config.time_budget.total_days,
            "max_journey_hours": config.time_budget.max_journey_hours,
        },
        "cost_budget": {
            "max_total": config.cost_budget.max_total,
            "max_per_leg": config.cost_budget.max_per_leg,
            "currency": config.cost_budget.currency,
        },
        "flight_options_count": len(results.flight_options),
        "top_flights": flights_summary,
        "transport_options": transport_summary or None,
        "travel_agent_findings": results.travel_agent_findings,
        "search_duration_seconds": results.search_duration_seconds,
    }

    return json.dumps(context, indent=2, default=str)


async def generate_summary(
    config: VoyageConfig, results: VoyageResults
) -> str:
    """Generate a one-shot summary of voyage results."""
    try:
        import litellm
    except ImportError:
        return _fallback_summary(config, results)

    llm_config = get_config().llm
    model_str = llm_config.model
    if llm_config.provider and llm_config.provider != "openai":
        model_str = f"{llm_config.provider}/{llm_config.model}"

    context = _build_results_context(config, results)
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Summarize these voyage search results:\n\n{context}"},
    ]

    try:
        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
        )
        return response.choices[0].message.content or _fallback_summary(config, results)
    except Exception as e:
        logger.error("Summary agent LLM call failed: %s", e)
        return _fallback_summary(config, results)


async def stream_summary(
    config: VoyageConfig, results: VoyageResults
) -> AsyncIterator[str]:
    """Stream summary tokens as they arrive from the LLM."""
    try:
        import litellm
    except ImportError:
        yield _fallback_summary(config, results)
        return

    llm_config = get_config().llm
    model_str = llm_config.model
    if llm_config.provider and llm_config.provider != "openai":
        model_str = f"{llm_config.provider}/{llm_config.model}"

    context = _build_results_context(config, results)
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Summarize these voyage search results:\n\n{context}"},
    ]

    try:
        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        logger.error("Summary agent streaming failed: %s", e)
        yield _fallback_summary(config, results)


def _fallback_summary(config: VoyageConfig, results: VoyageResults) -> str:
    """Generate a basic summary without LLM when litellm is unavailable."""
    lines = [f"## Voyage: {config.name}", ""]
    n = len(results.flight_options)
    if n == 0:
        lines.append("No flight options were found for the given configuration.")
    else:
        lines.append(f"Found **{n}** flight option{'s' if n != 1 else ''}.")
        best = results.flight_options[0]
        lines.append(
            f"Best price: **{best.currency} {best.price:,.0f}** "
            f"({best.origin} -> {best.destination}, {best.num_stops} stop{'s' if best.num_stops != 1 else ''}, "
            f"{best.total_duration_minutes // 60}h {best.total_duration_minutes % 60}m)"
        )
        if n > 1:
            prices = [f.price for f in results.flight_options]
            lines.append(f"Price range: {best.currency} {min(prices):,.0f} - {max(prices):,.0f}")

    if results.transport_options:
        lines.append(f"\nAlso found **{len(results.transport_options)}** alternative transport options.")

    lines.append(f"\nSearch completed in {results.search_duration_seconds:.1f}s.")
    return "\n".join(lines)
