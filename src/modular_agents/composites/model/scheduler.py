"""SemaphoreScheduler: caps concurrent requests per endpoint and retries transient errors centrally."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from modular_agents.composites.helpers import abortable
from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.endpoint import RetryableError
from modular_agents.interfaces.routing import Scheduler


class SemaphoreScheduler(Scheduler):
    def __init__(self, limits: dict[str, int] | None = None, default_limit: int = 4, retries: int = 3):
        self.limits = limits or {}
        self.default_limit = default_limit
        self.retries = retries
        self.slots: dict[str, asyncio.Semaphore] = {}

    async def run[T](self, endpoint_id: str, fn: Callable[[], Awaitable[T]], signal: AbortSignal) -> T:
        slots = self.slots.setdefault(endpoint_id, asyncio.Semaphore(self.limits.get(endpoint_id, self.default_limit)))
        async with slots:
            for attempt in range(self.retries + 1):
                try:
                    return await fn()
                except RetryableError:
                    if attempt == self.retries:
                        raise
                    await abortable(asyncio.sleep(2**attempt), signal)
