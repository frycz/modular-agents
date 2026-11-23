"""Loop interface: advances a state until a stop condition, and what it gets and returns."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from .budget import Budget
from .cancellation import AbortSignal
from .events import EventBus
from .inbox import Inbox
from .messages import Message
from .model import Model, StopReason
from .policy import ContextPolicy
from .state import RunState
from .store import RunStore
from .tools import ToolSet


@dataclass
class RunContext:
    """Everything one run needs besides its state. Built for each run, so the loop never depends on the harness."""

    model: Model
    budget: Budget
    signal: AbortSignal
    tools: ToolSet | None = None
    policy: ContextPolicy | None = None
    events: EventBus | None = None
    store: RunStore | None = None
    inbox: Inbox | None = None  # none: nothing can be added while the run is going


@dataclass
class RunOutcome:
    reason: StopReason | Literal["budget_exhausted", "cancelled", "blocked"]  # blocked: a prompt hook denied the task
    final: Message
    state: RunState


class Loop(ABC):
    @abstractmethod
    async def run(self, state: RunState, ctx: RunContext) -> RunOutcome:
        """Advance the state until a stop condition."""
