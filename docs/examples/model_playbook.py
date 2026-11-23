"""PlaybookModel: a scripted model for tests and offline runs."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.tools import Tool


class RollDie(Tool):
    definition = {
        "name": "roll_die",
        "description": "Roll a six-sided die.",
        "input_schema": {"type": "object", "properties": {}},
    }

    async def execute(self, input, ctx=None):
        return text_output(text="4")  # a fair roll, chosen by a fair die


# --8<-- [start:playbooks]
model = PlaybookModel(ref="playbook:games", playbooks={
    # keyword in the task -> one turn per model call
    "greet": [say("Hello!")],
    "dice": [
        [call("roll_die"), call("roll_die")],  # a list: several tool calls in one turn
        say(lambda results: f"You rolled {results[0]} and {results[1]}."),  # built from the tool results so far
    ],
})
# --8<-- [end:playbooks]


async def main():
    agent = ComposedAgent(
        model=model,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 5}), tools=StaticToolSet(tools=[RollDie()])),
    )
    # --8<-- [start:run]
    for task in ["Please greet me.", "Throw two dice.", "Tell me a joke."]:
        outcome = await agent.run(task)
        print(f"{task} -> {message_text(outcome.final)}")
    # --8<-- [end:run]


asyncio.run(main())
