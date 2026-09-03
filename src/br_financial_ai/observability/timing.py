from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class LatencyTracker:
    samples: dict[str, float] = field(default_factory=dict)

    @asynccontextmanager
    async def measure(self, name: str) -> AsyncIterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - started
            self.samples[name] = self.samples.get(name, 0.0) + elapsed

    def seconds(self, name: str) -> float | None:
        return self.samples.get(name)


class TimedYahooMarketClient:
    def __init__(self, inner: object, tracker: LatencyTracker) -> None:
        self._inner = inner
        self._tracker = tracker

    async def get_quote(self, ticker: str):
        async with self._tracker.measure("yahoo_quote_latency"):
            return await self._inner.get_quote(ticker)

    async def get_price_history(self, ticker: str, *, period: str):
        async with self._tracker.measure("yahoo_history_latency"):
            return await self._inner.get_price_history(ticker, period=period)


class TimedNewsClassifier:
    def __init__(self, inner: object, tracker: LatencyTracker) -> None:
        self._inner = inner
        self._tracker = tracker

    async def classify(self, request):
        async with self._tracker.measure("news_classification_latency"):
            return await self._inner.classify(request)

    async def classify_many(self, requests):
        async with self._tracker.measure("news_classification_latency"):
            return await self._inner.classify_many(requests)
