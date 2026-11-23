"""A harness with every part, shared by two agents with different models."""

import asyncio
import json
from dataclasses import asdict, replace

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.state import RunState
from modular_agents.interfaces.store import RunStore
from modular_agents.interfaces.tools import Tool

NOTES = {"groceries": "milk, eggs, coffee"}


class ReadNote(Tool):
    readonly = concurrent = True
    definition = {
        "name": "read_note",
        "description": "Read one note by its title.",
        "input_schema": schema(title="The title of the note."),
    }

    async def execute(self, input, ctx=None):
        return text_output(text=NOTES.get(input["title"], "no such note"))


class NoteIndexPolicy(ContextPolicy):
    async def prepare(self, state, prompt, model):
        return replace(prompt, system=f"{prompt.system}\n\nNotes available: {', '.join(sorted(NOTES))}")


class MemoryRunStore(RunStore):
    def __init__(self):
        self.runs = {}

    async def save(self, state):
        self.runs[state.id] = json.dumps(asdict(state))

    async def load(self, id):
        return RunState(**json.loads(self.runs[id])) if id in self.runs else None


# --8<-- [start:harness]
store = MemoryRunStore()
harness = Harness(
    loop=StandardLoop(),  # how a run advances
    budget=TreeBudget(limit={"steps": 6, "tokens": 50_000}),  # the limit of each run
    tools=StaticToolSet(tools=[ReadNote()]),  # what the model can do
    policy=NoteIndexPolicy(),  # what the model sees
    events=TranscriptBus(label="notes"),  # who watches and who may intervene
    store=store,  # where runs are saved
)
# --8<-- [end:harness]

# --8<-- [start:agents]
terse = PlaybookModel(ref="playbook:terse", playbooks={
    "groceries": [call("read_note", title="groceries"), say(lambda results: results[-1])],
})
chatty = PlaybookModel(ref="playbook:chatty", playbooks={
    "groceries": [
        call("read_note", title="groceries"),
        say(lambda results: f"Your groceries list says: {results[-1]}. Anything else?"),
    ],
})
terse_agent = ComposedAgent(model=terse, harness=harness)
chatty_agent = ComposedAgent(model=chatty, harness=harness)


async def main():
    for agent in (terse_agent, chatty_agent):
        outcome = await agent.run("What is on the groceries list?")
        print(message_text(outcome.final))
    print(f"{len(store.runs)} runs saved")


asyncio.run(main())
# --8<-- [end:agents]
