"""An agent: one conversation, continued on every run, with lifecycle and cancellation."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool


class Wait(Tool):
    definition = {"name": "wait", "description": "Wait a moment.", "input_schema": {"type": "object", "properties": {}}}

    async def execute(self, input, ctx=None):
        await asyncio.sleep(0.05)
        return text_output(text="waited")


model = PlaybookModel(ref="playbook:assistant", playbooks={
    "name is": [say("Nice to meet you, Ada.")],
    "my name": [say("Your name is Ada.")],
    "wait": [call("wait")] * 20 + [say("Done waiting.")],
})


async def main():
    # --8<-- [start:runs]
    agent = ComposedAgent(
        model=model,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 25}), tools=StaticToolSet(tools=[Wait()])),
        initial_state=InitialState(system="You are a friendly assistant."),
    )
    async with agent:  # starts the model and the tools, and closes them at the end
        first = await agent.run("Hi, my name is Ada.")
        second = await agent.run("What is my name?")  # the same conversation continues

    print(message_text(first.final))
    print(message_text(second.final))
    print(second.reason, len(second.state.messages), "messages")
    # --8<-- [end:runs]

    # --8<-- [start:cancel]
    signal = asyncio.Event()
    run = asyncio.create_task(agent.run("Wait twenty times.", signal))
    await asyncio.sleep(0.3)
    signal.set()  # cancels the run, and every sub-agent it started
    outcome = await run
    print(outcome.reason)
    # --8<-- [end:cancel]


asyncio.run(main())
