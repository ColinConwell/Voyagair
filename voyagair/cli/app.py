"""Voyagair CLI application."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from voyagair.core.config import get_config
from voyagair.core.search.models import CabinClass, SearchParams, SortKey

app = typer.Typer(
    name="voyagair",
    help="Optimized, configurable path-of-least-resistance travel planner and flight finder.",
    no_args_is_help=True,
)
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
    from voyagair.core.search.orchestrator import SearchOrchestrator

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

    async def _run():
        try:
            return await orchestrator.search(params)
        finally:
            await orchestrator.close()

    with console.status("[bold]Searching flights...", spinner="dots"):
        results = asyncio.run(_run())

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


@app.command()
def plan(
    origin: str = typer.Argument(..., help="Origin airport IATA code"),
    destination: str = typer.Argument(..., help="Final destination airport IATA code"),
    waypoints: Optional[str] = typer.Option(None, "--waypoints", "-w", help="Comma-separated waypoint airports"),
    avoid: Optional[str] = typer.Option(None, "--avoid", help="Conflict zones to avoid: middle_east, ukraine"),
    max_stops: int = typer.Option(3, "--max-stops", "-s", help="Max intermediate stops for route finding"),
    suggest_departures: Optional[str] = typer.Option(
        None, "--suggest-from", help="Comma-separated airports to compare as departure points"
    ),
) -> None:
    """Plan a multi-stop trip with route optimization and conflict-zone avoidance."""
    from voyagair.core.graph.airports import get_airport_db
    from voyagair.core.graph.route_graph import RouteGraph
    from voyagair.core.graph.solver import RouteSolver

    async def _run():
        config = get_config()
        with console.status("[bold]Loading airport database...", spinner="dots"):
            db = await get_airport_db(config.data_dir)

        graph = RouteGraph(db)
        avoid_zones = [z.strip() for z in avoid.split(",")] if avoid else []

        with console.status("[bold]Building route graph...", spinner="dots"):
            graph.build(avoid_zones=avoid_zones)

        solver = RouteSolver(graph, db)

        if suggest_departures:
            airports_to_compare = [a.strip().upper() for a in suggest_departures.split(",")]
            suggestions = solver.suggest_departure_airports(
                airports_to_compare, destination.upper(), avoid_zones=avoid_zones
            )
            table = Table(title="Departure Airport Comparison", show_lines=True)
            table.add_column("Airport", style="cyan")
            table.add_column("City", style="green")
            table.add_column("Direct?", justify="center")
            table.add_column("Path", style="dim")
            table.add_column("Distance (km)", justify="right")
            table.add_column("Connections", justify="center")

            for s in suggestions:
                path_str = " -> ".join(s["shortest_path"]) if s["shortest_path"] else "No path"
                dist = f"{s['path_distance_km']:,.0f}" if s["path_distance_km"] else "N/A"
                table.add_row(
                    s["iata"], s["city"],
                    "Yes" if s["direct_route"] else "No",
                    path_str, dist, str(s["num_connections"]),
                )
            console.print(table)
            return

        if waypoints:
            wp_list = [w.strip().upper() for w in waypoints.split(",")]
            with console.status("[bold]Optimizing route...", spinner="dots"):
                result = solver.solve_optimal_order(origin.upper(), destination.upper(), wp_list)

            if result:
                console.print(Panel(
                    f"[bold cyan]{' -> '.join(result.stops)}[/bold cyan]\n"
                    f"Total distance: [yellow]{result.total_distance_km:,.0f} km[/yellow]",
                    title="Optimal Route",
                ))
                table = Table(title="Leg Details")
                table.add_column("Leg", style="dim")
                table.add_column("From", style="cyan")
                table.add_column("To", style="green")
                table.add_column("Distance", justify="right")
                table.add_column("Direct?", justify="center")

                for i, leg in enumerate(result.legs, 1):
                    table.add_row(
                        str(i),
                        f"{leg['origin']} ({leg['origin_name']})",
                        f"{leg['destination']} ({leg['destination_name']})",
                        f"{leg['distance_km']:,.0f} km",
                        "Yes" if leg["direct_route_exists"] else "No",
                    )
                console.print(table)
            else:
                console.print("[red]No viable route found.[/red]")
        else:
            with console.status("[bold]Finding routes...", spinner="dots"):
                routes = solver.find_routes_avoiding_zones(
                    origin.upper(), destination.upper(), avoid_zones, max_stops=max_stops
                )

            if routes:
                table = Table(title=f"Routes from {origin.upper()} to {destination.upper()}", show_lines=True)
                table.add_column("#", style="dim", width=4)
                table.add_column("Route", style="cyan")
                table.add_column("Stops", justify="center")
                table.add_column("Distance (km)", justify="right")

                for i, path in enumerate(routes[:10], 1):
                    route_str = " -> ".join(path)
                    dist = graph.path_distance(path)
                    table.add_row(str(i), route_str, str(len(path) - 2), f"{dist:,.0f}")
                console.print(table)
            else:
                console.print("[red]No routes found avoiding the specified zones.[/red]")

    asyncio.run(_run())


@app.command()
def airports(
    query: Optional[str] = typer.Argument(None, help="Search query (IATA code, name, or city)"),
    country: Optional[str] = typer.Option(None, "--country", "-c", help="Filter by country code (e.g. US, ZA, NA)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results to show"),
) -> None:
    """Browse and search airports."""
    from voyagair.core.graph.airports import get_airport_db

    async def _run():
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

    asyncio.run(_run())


@app.command()
def explore(
    prompt: Optional[str] = typer.Argument(
        None, help="Describe your travel scenario (or omit for interactive mode)",
    ),
    model: str = typer.Option("gpt-5.4", "--model", "-m", help="LLM model to use"),
    provider: str = typer.Option("openai", "--provider", help="LLM provider: openai, anthropic, ollama"),
) -> None:
    """AI-assisted interactive exploration of travel options."""

    async def _run():
        try:
            from voyagair.api.agent.agent import TravelAgent
        except ImportError:
            console.print("[red]AI agent requires litellm. Install with: pip install litellm[/red]")
            return

        agent = TravelAgent(model=model, provider=provider)

        if prompt:
            with console.status("[bold]Thinking...", spinner="dots"):
                response = await agent.chat(prompt)
            console.print(Panel(Markdown(response), title="Voyagair AI", border_style="cyan"))
            return

        console.print(Panel(
            "Welcome to Voyagair AI Explorer.\n"
            "Describe your travel scenario and I'll help you find the best options.\n"
            "Type 'quit' or 'exit' to leave.",
            title="Voyagair AI",
            border_style="cyan",
        ))

        while True:
            try:
                user_input = console.input("[bold cyan]You:[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.strip().lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            if not user_input.strip():
                continue
            with console.status("[bold]Thinking...", spinner="dots"):
                response = await agent.chat(user_input)
            console.print(Panel(Markdown(response), title="Voyagair AI", border_style="cyan"))

    asyncio.run(_run())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Auto-reload on changes"),
) -> None:
    """Start the Voyagair API server."""
    import uvicorn
    uvicorn.run("voyagair.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
