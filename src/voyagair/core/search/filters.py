"""Result filtering, deduplication, and sorting for search results."""

from __future__ import annotations

from voyagair.core.search.models import FlightOffer, SortKey, TransportOption


def deduplicate_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    """Remove duplicate offers based on route + carrier + time signature."""
    seen: set[str] = set()
    unique: list[FlightOffer] = []
    for offer in offers:
        legs_sig = "|".join(
            f"{l.origin}-{l.destination}-{l.carrier}-{l.departure.isoformat() if l.departure else ''}"
            for l in offer.legs
        )
        key = f"{legs_sig}:{offer.price:.0f}"
        if key not in seen:
            seen.add(key)
            unique.append(offer)
    return unique


def filter_offers(
    offers: list[FlightOffer],
    max_price: float | None = None,
    max_stops: int | None = None,
    max_duration_hours: int | None = None,
    carriers: list[str] | None = None,
) -> list[FlightOffer]:
    """Apply filters to a list of flight offers."""
    result = offers
    if max_price is not None:
        result = [o for o in result if o.price <= max_price]
    if max_stops is not None:
        result = [o for o in result if o.num_stops <= max_stops]
    if max_duration_hours is not None:
        max_mins = max_duration_hours * 60
        result = [o for o in result if o.total_duration_minutes <= max_mins]
    if carriers:
        carrier_set = {c.upper() for c in carriers}
        result = [
            o for o in result
            if any(leg.carrier.upper() in carrier_set for leg in o.legs)
        ]
    return result


def sort_offers(offers: list[FlightOffer], sort_by: SortKey = SortKey.PRICE) -> list[FlightOffer]:
    """Sort offers by the given key."""
    if sort_by == SortKey.PRICE:
        return sorted(offers, key=lambda o: o.price)
    elif sort_by == SortKey.DURATION:
        return sorted(offers, key=lambda o: o.total_duration_minutes)
    elif sort_by == SortKey.DEPARTURE:
        return sorted(offers, key=lambda o: o.departure or o.legs[0].departure if o.legs else "")
    elif sort_by == SortKey.ARRIVAL:
        return sorted(offers, key=lambda o: o.arrival or o.legs[-1].arrival if o.legs else "")
    elif sort_by == SortKey.STOPS:
        return sorted(offers, key=lambda o: o.num_stops)
    return offers
