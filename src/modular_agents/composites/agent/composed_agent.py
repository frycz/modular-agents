"""ComposedAgent: a model plus a harness, owning one context that every run continues."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace

from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import append_user
from modular_agents.composites.inbox.list_inbox import ListInbox
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.interfaces.agent import Agent
from modular_agents.interfaces.budget import Budget
from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.events import Deny, Modify, PromptEvent
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.inbox import Inbox
from modular_agents.interfaces.loop import RunOutcome
from modular_agents.interfaces.messages import ContentBlock
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState, RunState


class ComposedAgent(Agent):
    def __init__(
        self, model: Model, harness: Harness | None = None, initial_state: InitialState | None = None,
        session_budget: Budget | None = None, state: RunState | None = None,
    ):
        self.model = model  # may be replaced between runs, e.g. by a /model command
        # the harness budget is each run's limit, it is never charged itself; without tools a run rarely needs more than one step
        self.harness = harness or Harness(StandardLoop(), TreeBudget({"steps": 25}))
        self.session_budget = session_budget or TreeBudget({})  # every run's spend is charged here too; none: no limit across runs
        initial = initial_state or InitialState()
        self._state = state or RunState(  # a saved state resumes that conversation, the initial state is then ignored
            system=initial.system, messages=copy.deepcopy(initial.messages),  # the initial state can be reused
            budget=self.harness.budget.remaining(), meta={"model": model.ref},
        )
        self._inbox = ListInbox()
        self._lock = asyncio.Lock()  # concurrent runs would interleave the context, so they take turns

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def inbox(self) -> Inbox:
        return self._inbox

    async def run(self, task: str | list[ContentBlock], signal: AbortSignal | None = None) -> RunOutcome:
        async with self._lock:
            content: list[ContentBlock] = [{"type": "text", "text": task}] if isinstance(task, str) else list(task)
            if events := self.harness.events:
                event: PromptEvent = {"type": "prompt", "run_id": self._state.id, "content": content}
                events.emit(event)
                decision = await events.intercept(event)
                if isinstance(decision, Deny):  # nothing is added to the context
                    final = {"role": "assistant", "content": [{"type": "text", "text": decision.reason or "the task was blocked"}]}
                    return RunOutcome("blocked", final, self._state)
                if isinstance(decision, Modify):
                    content = decision.value
            append_user(self._state.messages, content)  # joins e.g. tool results from a run that hit its budget
            self._state.meta["model"] = self.model.ref
            # a fresh child budget per run, like spawn_agent does per sub-agent
            harness = replace(self.harness, budget=self.session_budget.child(self.harness.budget.remaining()))
            return await harness.run(self._state, self.model, signal or asyncio.Event(), self._inbox)

    async def start(self) -> None:
        await self.model.start()
        await self.harness.start()

    async def aclose(self) -> None:
        await self.harness.aclose()
        await self.model.aclose()
