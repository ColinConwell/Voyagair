"""CLI command: multi-stop trip planning with route optimization."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from voyagair.core.config import get_config
from voyagair.core.graph.airports import get_airport_db
from voyagair.core.graph.route_graph import RouteGraph
from voyagair.core.graph.solver import RouteSolver
from voyagair.core.search.models import SortKey

app = typer.Typer(invoke_without_command=True)
console = Console()


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
    asyncio.run(_run_plan(origin, destination, waypoints, avoid, max_stops, suggest_departures))


async def _run_plan(
    origin: str,
    destination: str,
    waypoints: str | None,
    avoid: str | None,
    max_stops: int,
    suggest_departures: str | None,
) -> None:
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
