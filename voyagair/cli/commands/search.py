"""CLI command: search flights between airports."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from voyagair.core.config import get_config
from voyagair.core.search.models import CabinClass, SearchParams, SortKey
from voyagair.core.search.orchestrator import SearchOrchestrator

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.command()
def search(
    origins: str = typer.Argument(..., help="Origin airport(s), comma-separated (e.g. CPT,JNB)"),
    destinations: str = typer.Argument(..., help="Destination airport(s), comma-separated (e.g. JFK,EWR)"),
    dates: str = typer.Argument(..., help="Departure date(s), comma-separated (YYYY-MM-DD)"),
    adults: int = typer.Option(1, "--adults", "-a", help="Number of adult passengers"),
    cabin: str = typer.Option("economy", "--cabin", "-c", help="Cabin class: economy, premium_economy, business, first"),
    max_price: Optional[float] = typer.Option(None, "--max-price", "-p", help="Maximum price filter"),
    max_stops: Optional[int] = typer.Option(None, "--max-stops", "-s", help="Maximum number of stops"),
    sort: str = typer.Option("price", "--sort", help="Sort by: price, duration, departure, stops"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to display"),
    currency: str = typer.Option("USD", "--currency", help="Currency code"),
    providers: Optional[str] = typer.Option(None, "--providers", help="Comma-separated provider names to use"),
) -> None:
    """Search for flights between airports."""
    origin_list = [o.strip().upper() for o in origins.split(",")]
    dest_list = [d.strip().upper() for d in destinations.split(",")]
    date_list = [date.fromisoformat(d.strip()) for d in dates.split(",")]

    try:
        cabin_class = CabinClass(cabin.lower())
    except ValueError:
        cabin_class = CabinClass.ECONOMY

    try:
        sort_key = SortKey(sort.lower())
    except ValueError:
        sort_key = SortKey.PRICE

    params = SearchParams(
        origins=origin_list,
        destinations=dest_list,
        departure_dates=date_list,
        adults=adults,
        cabin_class=cabin_class,
        max_price=max_price,
        max_stops=max_stops,
        currency=currency,
        sort_by=sort_key,
        limit=limit,
        providers=[p.strip() for p in providers.split(",")] if providers else None,
    )

    config = get_config()
    orchestrator = SearchOrchestrator.from_config(config)

    with console.status("[bold]Searching flights...", spinner="dots"):
        results = asyncio.run(_run_search(orchestrator, params))

    if not results:
        console.print("[yellow]No flights found matching your criteria.[/yellow]")
        return

    table = Table(title=f"Flight Results ({len(results)} found)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Route", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Carrier", style="blue")
    table.add_column("Stops", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Price", justify="right", style="bold yellow")
    table.add_column("Provider", style="dim")

    for i, offer in enumerate(results, 1):
        route = f"{offer.origin} -> {offer.destination}"
        dep = offer.departure.strftime("%Y-%m-%d %H:%M") if offer.departure else "N/A"
        carriers = ", ".join(set(leg.carrier for leg in offer.legs if leg.carrier))
        stops = str(offer.num_stops)
        hours, mins = divmod(offer.total_duration_minutes, 60)
        duration = f"{hours}h {mins}m" if hours else f"{mins}m"
        price = f"{offer.currency} {offer.price:,.0f}"

        table.add_row(str(i), route, dep, carriers, stops, duration, price, offer.provider)

    console.print(table)


async def _run_search(orchestrator: SearchOrchestrator, params: SearchParams):
    try:
        return await orchestrator.search(params)
    finally:
        await orchestrator.close()
