# Flight Search Provider Development

Use this skill when:
- Adding a new flight search API provider
- Modifying existing provider behavior
- Debugging provider-specific search issues

## Provider Interface

All providers implement `voyagair.core.providers.base.Provider`:

```python
class Provider(ABC):
    @abstractmethod
    async def search_flights(self, params: SearchParams) -> list[FlightOffer]:
        ...

    async def close(self) -> None:
        ...
```

## Key Files
- `voyagair/core/providers/base.py` - Abstract base class
- `voyagair/core/providers/` - Provider implementations
- `voyagair/core/search/orchestrator.py` - Fans out to all providers concurrently
- `voyagair/core/search/models.py` - SearchParams, FlightOffer models
- `voyagair/core/config.py` - Provider configuration

## Adding a New Provider

1. Create `voyagair/core/providers/my_provider.py`
2. Implement the `Provider` abstract class
3. Register in `SearchOrchestrator.from_config()` in `voyagair/core/search/orchestrator.py`
4. Add any required API keys to `.env.local`
5. Add rate limiting config if needed

## Data Models
- `SearchParams` - origin, destination, dates, passengers, cabin class
- `FlightOffer` - price, currency, legs (with carrier, times, stops), deep_link, provider
- `Leg` - origin, destination, departure, arrival, carrier, duration_minutes

## Rate Limiting
Each provider can have its own rate limit configured via pyrate-limiter.
