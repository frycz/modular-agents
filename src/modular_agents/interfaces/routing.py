"""Model access layer internals: how requests to an endpoint are paced."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from .cancellation import AbortSignal


class Scheduler(ABC):
    @abstractmethod
    async def run[T](self, endpoint_id: str, fn: Callable[[], Awaitable[T]], signal: AbortSignal) -> T: ...
