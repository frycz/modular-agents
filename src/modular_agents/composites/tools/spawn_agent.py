"""spawn_agent: a sub-agent is just a tool that runs a fresh context through a harness and returns its final answer."""

from __future__ import annotations

import copy
from dataclasses import replace

from modular_agents.composites.helpers import message_text
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState, RunState
from modular_agents.interfaces.tools import Tool, ToolContext, ToolOutput


class SpawnAgentTool(Tool):
    concurrent = True  # each sub-agent has its own context
    definition = {
        "name": "spawn_agent",
        "description": "Delegate a self-contained task to a sub-agent with a fresh context. Several can run in parallel.",
        "input_schema": schema(task="Everything the sub-agent needs to know to do the task."),
    }

    def __init__(self, model: Model, harness: Harness, initial_state: InitialState | None = None):
        self.model = model
        self.harness = harness  # its budget is the limit for each sub-agent, it is never charged itself
        self.initial = initial_state or InitialState()

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        if ctx is None:  # without a caller's budget there is nothing to hang the sub-agent's budget from
            raise ValueError("spawn_agent needs a ToolContext: its budget is the parent of the sub-agent's budget")
        # each sub-agent gets a fresh child of the caller's budget, so its spend also counts against the caller
        harness = replace(self.harness, budget=ctx.budget.child(self.harness.budget.remaining()))
        task = {"role": "user", "content": [{"type": "text", "text": input["task"]}]}
        state = RunState(
            system=self.initial.system, messages=copy.deepcopy(self.initial.messages) + [task],
            budget=harness.budget.remaining(), meta={"model": self.model.ref}, parent_id=ctx.run_id,
        )
        outcome = await harness.run(state, self.model, ctx.signal)  # same signal: cancelling the parent cancels the child
        return text_output(message_text(outcome.final) or f"(sub-agent stopped: {outcome.reason})")

    async def start(self) -> None:
        await self.model.start()
        await self.harness.start()

    async def aclose(self) -> None:
        await self.harness.aclose()
        await self.model.aclose()
