"""Harness: everything around the model. The loop, the budget and the optional parts."""

from __future__ import annotations

from dataclasses import dataclass

from .budget import Budget
from .cancellation import AbortSignal
from .events import EventBus
from .inbox import Inbox
from .loop import Loop, RunContext, RunOutcome
from .model import Model
from .policy import ContextPolicy
from .state import RunState
from .store import RunStore
from .tools import ToolSet


@dataclass
class Harness:
    loop: Loop
    budget: Budget  # required: an agent always has a stop condition
    tools: ToolSet | None = None  # none: the model can only answer in text
    policy: ContextPolicy | None = None  # none: the model sees the context as it is
    events: EventBus | None = None  # none: nothing observed, every tool call allowed
    store: RunStore | None = None  # none: nothing persisted

    async def run(self, state: RunState, model: Model, signal: AbortSignal, inbox: Inbox | None = None) -> RunOutcome:
        """Hand the harness parts to the loop as one RunContext."""
        ctx = RunContext(model, self.budget, signal, self.tools, self.policy, self.events, self.store, inbox)
        return await self.loop.run(state, ctx)

    async def start(self) -> None:
        if self.tools:
            await self.tools.start()

    async def aclose(self) -> None:
        if self.tools:
            await self.tools.aclose()
