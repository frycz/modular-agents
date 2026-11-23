"""Run store: persists run states, so runs can be inspected or resumed."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .state import RunState


class RunStore(ABC):
    @abstractmethod
    async def save(self, state: RunState) -> None: ...

    @abstractmethod
    async def load(self, id: str) -> RunState | None: ...
