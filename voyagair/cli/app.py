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


@app.command(name="app")
def launch_app(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """Launch the vanilla web app and open it in your browser."""
    import webbrowser

    import uvicorn

    url = f"http://localhost:{port}/app"
    if not no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    console.print(f"[bold]Starting Voyagair app at {url}[/bold]")
    uvicorn.run("voyagair.api.app:app", host=host, port=port, reload=False)


voyage_app = typer.Typer(name="voyage", help="Manage voyage configurations.", no_args_is_help=True)
app.add_typer(voyage_app)


@voyage_app.command(name="new")
def voyage_new(
    name: str = typer.Option("Untitled Voyage", "--name", "-n", help="Name for the voyage"),
    origin: Optional[str] = typer.Option(None, "--from", help="Starting point (IATA code)"),
    destination: Optional[str] = typer.Option(None, "--to", help="End point (IATA code)"),
) -> None:
    """Create a new voyage configuration."""
    from voyagair.core.voyage.models import LocationSpec, LocationType, VoyageConfig
    from voyagair.core.voyage.store import get_voyage_store

    config = VoyageConfig(name=name)
    if origin:
        config.starting_points.append(
            LocationSpec(type=LocationType.AIRPORT, value=origin.upper(), label=origin.upper())
        )
    if destination:
        config.end_points.append(
            LocationSpec(type=LocationType.AIRPORT, value=destination.upper(), label=destination.upper())
        )

    store = get_voyage_store()
    voyage_id = store.save(config)
    console.print(f"[green]Created voyage:[/green] {config.name} ({voyage_id[:8]}...)")


@voyage_app.command(name="list")
def voyage_list() -> None:
    """List all saved voyages."""
    from voyagair.core.voyage.store import get_voyage_store

    store = get_voyage_store()
    voyages = store.list()

    if not voyages:
        console.print("[yellow]No saved voyages.[/yellow]")
        return

    table = Table(title=f"Saved Voyages ({len(voyages)})")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Name", style="cyan")
    table.add_column("Updated", style="green")

    for v in voyages:
        vid = v["id"][:8] + "..."
        table.add_row(vid, v["name"], v.get("updated_at", "")[:19])
    console.print(table)


@voyage_app.command(name="load")
def voyage_load(
    voyage_id: str = typer.Argument(..., help="Voyage ID (or prefix)"),
) -> None:
    """Load and display a saved voyage configuration."""
    from voyagair.core.voyage.store import get_voyage_store

    store = get_voyage_store()

    config = store.load(voyage_id)
    if config is None:
        voyages = store.list()
        matches = [v for v in voyages if v["id"].startswith(voyage_id)]
        if len(matches) == 1:
            config = store.load(matches[0]["id"])
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{voyage_id}':[/yellow]")
            for m in matches:
                console.print(f"  {m['id'][:8]}... {m['name']}")
            return
        else:
            console.print(f"[red]Voyage '{voyage_id}' not found.[/red]")
            return

    if config is None:
        console.print(f"[red]Failed to load voyage.[/red]")
        return

    starts = ", ".join(f"{s.type.value}:{s.value}" for s in config.starting_points) or "None"
    ends = ", ".join(f"{e.type.value}:{e.value}" for e in config.end_points) or "None"
    sites = ", ".join(f"{s.type.value}:{s.value}" for s in config.sites_along_the_way) or "None"

    console.print(Panel(
        f"[bold]{config.name}[/bold]\n"
        f"ID: [dim]{config.id}[/dim]\n"
        f"From: [cyan]{starts}[/cyan]\n"
        f"To: [cyan]{ends}[/cyan]\n"
        f"Sites: {sites}\n"
        f"Dates: {config.departure_date or 'TBD'} - {config.return_date or 'TBD'}\n"
        f"Budget: {config.cost_budget.currency} {config.cost_budget.max_total or 'unlimited'}\n"
        f"Time: {config.time_budget.total_days} days\n"
        f"Agent: {'Enabled' if config.travel_agent.enabled else 'Disabled'}",
        title="Voyage Configuration",
        border_style="cyan",
    ))


@voyage_app.command(name="delete")
def voyage_delete(
    voyage_id: str = typer.Argument(..., help="Voyage ID to delete"),
) -> None:
    """Delete a saved voyage."""
    from voyagair.core.voyage.store import get_voyage_store

    store = get_voyage_store()
    deleted = store.delete(voyage_id)
    if deleted:
        console.print(f"[green]Deleted voyage {voyage_id[:8]}...[/green]")
    else:
        console.print(f"[red]Voyage '{voyage_id}' not found.[/red]")


@voyage_app.command(name="parse")
def voyage_parse(
    config_file: str = typer.Argument(..., help="Path to config file (YAML, JSON, or Markdown)"),
) -> None:
    """Parse a config file and display the interpreted VoyageConfig."""
    from voyagair.core.voyage.config_parser import parse_config_file

    try:
        config = parse_config_file(config_file)
    except Exception as e:
        console.print(f"[red]Failed to parse config: {e}[/red]")
        raise typer.Exit(1)

    starts = ", ".join(f"{s.type.value}:{s.value}" for s in config.starting_points) or "None"
    ends = ", ".join(f"{e.type.value}:{e.value}" for e in config.end_points) or "None"
    sites = ", ".join(f"{s.label or s.value}" for s in config.sites_along_the_way) or "None"

    console.print(Panel(
        f"[bold]{config.name}[/bold]\n"
        f"From: [cyan]{starts}[/cyan]\n"
        f"To: [cyan]{ends}[/cyan]\n"
        f"Sites: {sites}\n"
        f"Date: {config.departure_date or 'TBD'}"
        f"{' (flexible)' if config.flexible_dates else ''}\n"
        f"Budget: {config.cost_budget.currency} {config.cost_budget.max_total or 'unlimited'}\n"
        f"Time: {config.time_budget.total_days} days\n"
        f"Avoid airlines: {', '.join(config.avoid_airlines) or 'None'}\n"
        f"Avoid regions: {', '.join(config.avoid_routing_regions) or 'None'}\n"
        f"Layover regions: {', '.join(config.layover_regions) or 'None'}\n"
        f"Notes: {(config.notes or 'None')[:200]}",
        title="Parsed Voyage Config",
        border_style="cyan",
    ))


@voyage_app.command(name="run")
def voyage_run(
    config_file: str = typer.Argument(..., help="Path to config file (YAML, JSON, or Markdown)"),
    fmt: str = typer.Option("html", "--format", "-f", help="Output format: html, md, pdf"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open the report in a browser"),
) -> None:
    """Run a full voyage pipeline: parse config, search, generate report."""
    from pathlib import Path

    from voyagair.core.voyage.config_parser import parse_config_file
    from voyagair.core.voyage.report import generate_report
    from voyagair.core.voyage.search import VoyageSearchOrchestrator
    from voyagair.core.voyage.summary_agent import generate_summary
    from voyagair.core.voyage.store import get_voyage_store

    try:
        config = parse_config_file(config_file)
    except Exception as e:
        console.print(f"[red]Failed to parse config: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Voyage:[/bold] {config.name}")
    console.print(f"  From: {', '.join(s.value for s in config.starting_points)}")
    console.print(f"  To: {', '.join(e.value for e in config.end_points)}")

    store = get_voyage_store()
    store.save(config)

    async def _run():
        app_config = get_config()
        search_orch = VoyageSearchOrchestrator(config=app_config)
        try:
            results = await search_orch.search(config)
        finally:
            await search_orch.close()

        try:
            results.agent_summary = await generate_summary(config, results)
        except Exception as e:
            console.print(f"[yellow]Summary generation skipped: {e}[/yellow]")

        return results

    with console.status("[bold]Searching flights and generating summary...", spinner="dots"):
        results = asyncio.run(_run())

    console.print(f"[green]Found {len(results.flight_options)} flights in {results.search_duration_seconds:.1f}s[/green]")

    refresh_url = f"/api/voyage/{config.id}/report"
    report = generate_report(config, results, fmt=fmt, refresh_url=refresh_url)

    ext_map = {"html": ".html", "md": ".md", "pdf": ".pdf"}
    if output is None:
        slug = config.name.lower().replace(" ", "-")[:30]
        output = f"{slug}-report{ext_map.get(fmt, '.html')}"

    out_path = Path(output)
    if isinstance(report, bytes):
        out_path.write_bytes(report)
    else:
        out_path.write_text(report, encoding="utf-8")

    console.print(f"[green]Report saved to:[/green] {out_path}")

    if not no_open and fmt == "html":
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")


if __name__ == "__main__":
    app()
