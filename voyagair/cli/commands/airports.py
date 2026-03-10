"""CLI command: browse and search airports."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.command()
def airports(
    query: Optional[str] = typer.Argument(None, help="Search query (IATA code, name, or city)"),
    country: Optional[str] = typer.Option(None, "--country", "-c", help="Filter by country code (e.g. US, ZA, NA)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results to show"),
) -> None:
    """Browse and search airports."""
    asyncio.run(_run_airports(query, country, limit))


async def _run_airports(query: str | None, country: str | None, limit: int) -> None:
    config = get_config()
    with console.status("[bold]Loading airport database...", spinner="dots"):
        db = await get_airport_db(config.data_dir)

    if query:
        results = db.search(query)
    elif country:
        results = db.get_by_country(country.upper())
    else:
        console.print("[yellow]Provide a search query or --country filter.[/yellow]")
        console.print("Examples:")
        console.print("  voyagair airports JFK")
        console.print("  voyagair airports 'cape town'")
        console.print("  voyagair airports --country ZA")
        return

    if not results:
        console.print("[yellow]No airports found.[/yellow]")
        return

    results = results[:limit]

    table = Table(title=f"Airports ({len(results)} results)")
    table.add_column("IATA", style="bold cyan")
    table.add_column("ICAO", style="dim")
    table.add_column("Name", style="green")
    table.add_column("City")
    table.add_column("Country")
    table.add_column("Lat", justify="right", style="dim")
    table.add_column("Lon", justify="right", style="dim")

    for ap in results:
        table.add_row(
            ap.iata, ap.icao, ap.name, ap.city, ap.country_code,
            f"{ap.latitude:.2f}", f"{ap.longitude:.2f}",
        )
    console.print(table)
