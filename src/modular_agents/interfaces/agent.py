"""Agent interface: an agent owns one context and advances it."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .cancellation import AbortSignal
from .inbox import Inbox
from .lifecycle import Resource
from .loop import RunOutcome
from .messages import ContentBlock
from .state import RunState


class Agent(Resource, ABC):
    """Use as `async with agent:` so its tools and model are started and closed."""

    @property
    @abstractmethod
    def state(self) -> RunState:
        """The agent's context. Read-only by convention."""

    @property
    @abstractmethod
    def inbox(self) -> Inbox:
        """Content put here while a run is going is added to the context before the next model call."""

    @abstractmethod
    async def run(self, task: str | list[ContentBlock], signal: AbortSignal) -> RunOutcome:
        """Append task to the context, then run the loop until a stop condition."""
