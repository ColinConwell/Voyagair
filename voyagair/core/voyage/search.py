"""Voyage search orchestrator: resolves config into search params and runs searches."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date

from voyagair.core.config import VoyagairConfig, get_config
from voyagair.core.graph.airports import AirportDatabase, get_airport_db
from voyagair.core.graph.route_graph import RouteGraph
from voyagair.core.graph.solver import RouteSolver
from voyagair.core.search.models import FlightOffer, SearchParams, TransportOption
from voyagair.core.search.orchestrator import SearchOrchestrator
from voyagair.core.voyage.models import VoyageConfig, VoyageResults
from voyagair.core.voyage.resolver import resolve_locations

logger = logging.getLogger(__name__)


class VoyageSearchOrchestrator:
    """Accepts a VoyageConfig and executes a full search pipeline."""

    def __init__(
        self,
        config: VoyagairConfig | None = None,
        orchestrator: SearchOrchestrator | None = None,
    ):
        self._config = config or get_config()
        self._orchestrator = orchestrator or SearchOrchestrator.from_config(self._config)
        self._db: AirportDatabase | None = None

    async def _get_db(self) -> AirportDatabase:
        if self._db is None:
            self._db = await get_airport_db(self._config.data_dir)
        return self._db

    async def search(self, voyage: VoyageConfig) -> VoyageResults:
        """Run the full voyage search pipeline."""
        start = time.monotonic()
        db = await self._get_db()

        origins = await resolve_locations(voyage.starting_points, db)
        destinations = await resolve_locations(voyage.end_points, db)

        if not origins or not destinations:
            return VoyageResults(
                voyage_id=voyage.id,
                agent_summary="No airports resolved from the given starting/end points.",
            )

        waypoint_codes: list[str] = []
        if voyage.sites_along_the_way:
            waypoint_codes = await resolve_locations(voyage.sites_along_the_way, db)

        optimized_order: list[str] | None = None
        if waypoint_codes and len(origins) == 1 and len(destinations) == 1:
            try:
                graph = RouteGraph(db)
                graph.build()
                solver = RouteSolver(graph, db)
                plan = solver.solve_optimal_order(
                    origins[0], destinations[0], waypoint_codes
                )
                if plan:
                    optimized_order = plan.stops
            except Exception:
                logger.warning("Waypoint optimization failed, proceeding without it")

        dep_dates = []
        if voyage.departure_date:
            try:
                dep_dates.append(date.fromisoformat(voyage.departure_date))
            except ValueError:
                pass
        if not dep_dates:
            dep_dates.append(date.today())

        max_price = voyage.cost_budget.max_per_leg or voyage.cost_budget.max_total
        max_duration = None
        if voyage.time_budget.max_journey_hours:
            max_duration = int(voyage.time_budget.max_journey_hours)

        if optimized_order and len(optimized_order) > 2:
            all_flights, all_transport = await self._search_multi_stop(
                optimized_order, dep_dates, voyage, max_price, max_duration
            )
        else:
            all_flights, all_transport = await self._search_direct(
                origins, destinations, dep_dates, voyage, max_price, max_duration
            )

        elapsed = time.monotonic() - start
        return VoyageResults(
            voyage_id=voyage.id,
            flight_options=all_flights,
            transport_options=all_transport,
            search_duration_seconds=round(elapsed, 2),
        )

    async def _search_direct(
        self,
        origins: list[str],
        destinations: list[str],
        dep_dates: list[date],
        voyage: VoyageConfig,
        max_price: float | None,
        max_duration: int | None,
    ) -> tuple[list[FlightOffer], list[TransportOption]]:
        params = SearchParams(
            origins=origins,
            destinations=destinations,
            departure_dates=dep_dates,
            adults=voyage.adults,
            cabin_class=voyage.cabin_class,
            max_price=max_price,
            max_duration_hours=max_duration,
            sort_by=voyage.optimize_for,
            limit=50,
            currency=voyage.cost_budget.currency,
        )
        flights = await self._orchestrator.search(params)
        transport = await self._orchestrator.search_transport(params)
        return flights, transport

    async def _search_multi_stop(
        self,
        stop_order: list[str],
        dep_dates: list[date],
        voyage: VoyageConfig,
        max_price: float | None,
        max_duration: int | None,
    ) -> tuple[list[FlightOffer], list[TransportOption]]:
        """Search each leg of a multi-stop itinerary."""
        all_flights: list[FlightOffer] = []
        all_transport: list[TransportOption] = []

        tasks = []
        for i in range(len(stop_order) - 1):
            leg_origins = [stop_order[i]]
            leg_dests = [stop_order[i + 1]]
            params = SearchParams(
                origins=leg_origins,
                destinations=leg_dests,
                departure_dates=dep_dates,
                adults=voyage.adults,
                cabin_class=voyage.cabin_class,
                max_price=max_price,
                max_duration_hours=max_duration,
                sort_by=voyage.optimize_for,
                limit=20,
                currency=voyage.cost_budget.currency,
            )
            tasks.append(self._orchestrator.search(params))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Multi-stop leg search failed: %s", result)
                continue
            all_flights.extend(result)

        return all_flights, all_transport

    async def close(self) -> None:
        await self._orchestrator.close()
