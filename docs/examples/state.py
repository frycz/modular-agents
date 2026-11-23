"""The state of a run is data: it can be inspected, saved, loaded and resumed."""

import asyncio
import json
from dataclasses import asdict

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState, RunState
from modular_agents.interfaces.store import RunStore
from modular_agents.interfaces.tools import Tool


# --8<-- [start:remember]
class Remember(Tool):
    """Keeps facts in the run state, so they are saved and resumed with the conversation."""

    definition = {
        "name": "remember",
        "description": "Remember a fact for later.",
        "input_schema": schema(fact="The fact to remember."),
    }

    async def execute(self, input, ctx=None):
        facts = ctx.state.data.setdefault("facts", [])
        facts.append(input["fact"])
        return text_output(text=f"remembered ({len(facts)} facts)")
# --8<-- [end:remember]


# --8<-- [start:store]
class MemoryRunStore(RunStore):
    """Keeps every run as JSON in a dict. A file or a database works the same way."""

    def __init__(self):
        self.runs: dict[str, str] = {}

    async def save(self, state):
        self.runs[state.id] = json.dumps(asdict(state))

    async def load(self, id):
        saved = self.runs.get(id)
        return RunState(**json.loads(saved)) if saved else None
# --8<-- [end:store]


model = PlaybookModel(ref="playbook:memory", playbooks={
    "remember": [call("remember", fact="the meeting is on Friday"), say("Noted.")],
    "when": [say("The meeting is on Friday.")],
})
store = MemoryRunStore()
harness = Harness(
    loop=StandardLoop(),
    budget=TreeBudget(limit={"steps": 5}),
    tools=StaticToolSet(tools=[Remember()]),
    store=store,
)


async def main():
    # --8<-- [start:run]
    agent = ComposedAgent(
        model=model,
        harness=harness,
        initial_state=InitialState(system="You are a meeting assistant."),
    )
    await agent.run("Please remember that the meeting is on Friday.")

    state = agent.state
    print("id:", state.id)
    print("messages:", len(state.messages))
    print("data:", state.data)
    print("budget left:", state.budget["steps"], "steps")
    # --8<-- [end:run]

    # --8<-- [start:resume]
    saved = await store.load(state.id)  # for example in another process, the next day
    resumed = ComposedAgent(model=model, harness=harness, state=saved)
    outcome = await resumed.run("When is the meeting?")
    print(message_text(outcome.final))
    print("messages:", len(resumed.state.messages), "facts:", resumed.state.data["facts"])
    # --8<-- [end:resume]


asyncio.run(main())
