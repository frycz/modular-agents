"""Budgets: limits, child budgets and a run that hits its limit."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.tools import Tool

# --8<-- [start:tree]
parent = TreeBudget(limit={"steps": 10, "tokens": 5_000})
child = parent.child({"steps": 3})  # a sub-agent's budget, capped by what the parent has left

usage = {"input_tokens": 1_500, "output_tokens": 500, "cost_usd": 0.0, "elapsed_ms": 900.0}
child.charge(usage)  # one model call of the sub-agent, charged to the parent too

print("parent spent:", parent.spent)
print("child left:", child.remaining())
# --8<-- [end:tree]


class Ping(Tool):
    definition = {"name": "ping", "description": "Ping.", "input_schema": {"type": "object", "properties": {}}}

    async def execute(self, input, ctx=None):
        return text_output(text="pong")


async def main():
    # --8<-- [start:exhausted]
    restless = PlaybookModel(ref="playbook:restless", playbooks={"ping": [call("ping")] * 100})
    agent = ComposedAgent(
        model=restless,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 3}), tools=StaticToolSet(tools=[Ping()])),
    )
    outcome = await agent.run("Ping forever.")
    print(outcome.reason, "after", len(outcome.state.messages), "messages")
    # --8<-- [end:exhausted]

    # --8<-- [start:session]
    session = TreeBudget(limit={"steps": 4})  # across all runs of the agent
    agent = ComposedAgent(
        model=restless,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 3}), tools=StaticToolSet(tools=[Ping()])),
        session_budget=session,
    )
    for run in range(1, 4):
        outcome = await agent.run("Ping again.")
        print(f"run {run}: {outcome.reason}, session spent {session.spent['steps']} steps")
    # --8<-- [end:session]


asyncio.run(main())
