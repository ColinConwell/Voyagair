"""Report exporter: generates HTML, Markdown, and PDF reports from voyage results."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from voyagair.core.voyage.models import VoyageConfig, VoyageResults

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _prepare_flights(results: VoyageResults) -> list[dict]:
    """Flatten flight offers into template-friendly dicts."""
    flights = []
    for offer in results.flight_options:
        legs = offer.legs
        origin = legs[0].origin if legs else "?"
        destination = legs[-1].destination if legs else "?"
        departure = legs[0].departure if legs else None
        carriers = ", ".join(sorted({l.carrier for l in legs if l.carrier}))
        num_stops = max(0, len(legs) - 1)

        total_min = sum(l.duration_minutes for l in legs)
        if total_min == 0 and len(legs) >= 2:
            delta = (legs[-1].arrival - legs[0].departure).total_seconds()
            total_min = int(max(0, delta) / 60)

        h, m = divmod(total_min, 60)
        duration_str = f"{h}h {m}m" if h else f"{m}m"

        dep_str = departure.strftime("%b %d %H:%M") if departure else "N/A"
        dep_iso = departure.isoformat() if departure else ""

        stops_class = "stops-0" if num_stops == 0 else "stops-1" if num_stops == 1 else "stops-2"
        stops_label = "Nonstop" if num_stops == 0 else f"{num_stops} stop{'s' if num_stops > 1 else ''}"

        flights.append({
            "origin": origin,
            "destination": destination,
            "departure_str": dep_str,
            "departure_iso": dep_iso,
            "carriers": carriers or "N/A",
            "num_stops": num_stops,
            "stops_class": stops_class,
            "stops_label": stops_label,
            "duration_str": duration_str,
            "total_minutes": total_min,
            "price": offer.price,
            "currency": offer.currency,
            "deep_link": offer.deep_link or offer.booking_url or "",
            "provider": offer.provider,
        })
    return flights


def _origins_label(config: VoyageConfig) -> str:
    return ", ".join(f"{s.label or s.value}" for s in config.starting_points) or "N/A"


def _destinations_label(config: VoyageConfig) -> str:
    return ", ".join(f"{e.label or e.value}" for e in config.end_points) or "N/A"


def generate_report(
    config: VoyageConfig,
    results: VoyageResults,
    fmt: str = "html",
    refresh_url: str | None = None,
) -> str | bytes:
    """Generate a voyage report in the specified format.

    Args:
        config: The voyage configuration.
        results: Search results.
        fmt: Output format -- "html", "md", or "pdf".
        refresh_url: Optional API URL for auto-refresh (HTML only).

    Returns:
        Rendered report as a string (html/md) or bytes (pdf).
    """
    if fmt == "html":
        return _generate_html(config, results, refresh_url)
    if fmt in ("md", "markdown"):
        return _generate_markdown(config, results)
    if fmt == "pdf":
        return _generate_pdf(config, results)
    raise ValueError(f"Unsupported report format: {fmt}")


def _generate_html(
    config: VoyageConfig,
    results: VoyageResults,
    refresh_url: str | None = None,
) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    template = env.get_template("report.html")

    flights = _prepare_flights(results)
    flight_dates = sorted({f["departure_iso"][:10] for f in flights if f["departure_iso"]})

    flights_json = json.dumps(flights, default=str)

    return template.render(
        config=config,
        flights=flights,
        flights_json=flights_json,
        flight_dates=flight_dates,
        flight_count=len(flights),
        summary=results.agent_summary or "",
        origins_label=_origins_label(config),
        destinations_label=_destinations_label(config),
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        refresh_url=refresh_url or "",
    )


def _generate_markdown(config: VoyageConfig, results: VoyageResults) -> str:
    flights = _prepare_flights(results)
    lines: list[str] = []

    lines.append(f"# {config.name}")
    lines.append("")
    lines.append(f"**From:** {_origins_label(config)}  ")
    lines.append(f"**To:** {_destinations_label(config)}  ")
    lines.append(f"**Date:** {config.departure_date or 'Flexible'}"
                 f"{'  (flexible)' if config.flexible_dates else ''}  ")
    budget = config.cost_budget
    budget_str = f"{budget.currency} {budget.max_total:,.0f}" if budget.max_total else "Unlimited"
    lines.append(f"**Budget:** {budget_str}  ")
    if config.avoid_airlines:
        lines.append(f"**Avoid Airlines:** {', '.join(config.avoid_airlines)}  ")
    if config.avoid_routing_regions:
        lines.append(f"**Avoid Regions:** {', '.join(config.avoid_routing_regions)}  ")
    lines.append("")

    if results.agent_summary:
        lines.append("## Summary")
        lines.append("")
        lines.append(results.agent_summary)
        lines.append("")

    lines.append("## Flight Options")
    lines.append("")
    lines.append("| Route | Date | Carrier | Stops | Duration | Price | Book |")
    lines.append("|-------|------|---------|-------|----------|-------|------|")
    for f in flights:
        link = f"[Book]({f['deep_link']})" if f["deep_link"] else "--"
        lines.append(
            f"| {f['origin']} -> {f['destination']} "
            f"| {f['departure_str']} "
            f"| {f['carriers']} "
            f"| {f['stops_label']} "
            f"| {f['duration_str']} "
            f"| {f['currency']} {f['price']:,.0f} "
            f"| {link} |"
        )
    lines.append("")

    if flights:
        lines.append("## Calendar")
        lines.append("")
        by_date: dict[str, list[dict]] = {}
        for f in flights:
            d = f["departure_iso"][:10] if f["departure_iso"] else None
            if d:
                by_date.setdefault(d, []).append(f)
        for date_str in sorted(by_date):
            lines.append(f"### {date_str}")
            for fl in by_date[date_str]:
                link = f"[{fl['origin']}->{fl['destination']} ${fl['price']:,.0f}]({fl['deep_link']})" if fl["deep_link"] else f"{fl['origin']}->{fl['destination']} ${fl['price']:,.0f}"
                lines.append(f"- {link} ({fl['carriers']}, {fl['duration_str']}, {fl['stops_label']})")
            lines.append("")

    lines.append(f"---\n*Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} by Voyagair*")
    return "\n".join(lines)


def _generate_pdf(config: VoyageConfig, results: VoyageResults) -> bytes:
    html = _generate_html(config, results)
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        raise ImportError(
            "PDF generation requires weasyprint. Install with: pip install weasyprint"
        )
