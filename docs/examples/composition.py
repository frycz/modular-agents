"""Agents as tools: spawn_agent, blueprints and the agent tree."""

import asyncio

from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.composites.tools.spawn_agent import SpawnAgentTool
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool

NOTES = {"groceries": "milk, eggs, coffee", "ideas": "give every sub-agent its own budget"}


class ReadNote(Tool):
    readonly = concurrent = True
    definition = {
        "name": "read_note",
        "description": "Read one note by its title.",
        "input_schema": schema(title="The title of the note."),
    }

    async def execute(self, input, ctx=None):
        return text_output(text=NOTES.get(input["title"], "no such note"))


# Scripted models, so the example runs offline. Any Model works in their place.
reader_model = PlaybookModel(ref="playbook:reader", playbooks={
    "groceries": [call("read_note", title="groceries"), say(lambda r: f"groceries: {r[-1]}")],
    "ideas": [call("read_note", title="ideas"), say(lambda r: f"ideas: {r[-1]}")],
})
lead_model = PlaybookModel(ref="playbook:lead", playbooks={
    "both": [
        [call("spawn_agent", task="Read the groceries note."), call("spawn_agent", task="Read the ideas note.")],
        say(lambda r: " | ".join(r)),
    ],
})
editor_model = PlaybookModel(ref="playbook:editor", playbooks={
    "digest": [
        call("note_reader", task="Read the ideas note."),
        say(lambda r: f"Digest. {r[-1]}"),
    ],
})


async def main():
    # --8<-- [start:spawn]
    # The harness every sub-agent runs in: its budget is the limit of each sub-agent.
    sub_harness = Harness(
        loop=StandardLoop(),
        budget=TreeBudget(limit={"steps": 3}),
        tools=StaticToolSet(tools=[ReadNote()]),
        events=TranscriptBus(label="sub_agent"),
    )
    spawn = SpawnAgentTool(model=reader_model, harness=sub_harness, initial_state=InitialState(system="Read notes."))

    session = TreeBudget(limit={"steps": 20})
    lead_agent = ComposedAgent(
        model=lead_model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 10}),  # covers the sub-agents' steps too
            tools=StaticToolSet(tools=[spawn]),
            events=TranscriptBus(label="lead_agent"),
        ),
        session_budget=session,
    )
    outcome = await lead_agent.run("Read both notes.")
    print(message_text(outcome.final))
    print("steps in the whole tree:", session.spent["steps"])
    # --8<-- [end:spawn]

    # --8<-- [start:blueprint]
    note_reader = Blueprint(
        name="note_reader",
        description="reads notes and reports what they say.",
        model=reader_model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 3}),
            tools=StaticToolSet(tools=[ReadNote()]),
            events=TranscriptBus(label="note_reader"),
        ),
        initial=InitialState(system="Read notes and report what they say."),
    )
    editor = Blueprint(
        name="editor",
        description="writes digests of the notes.",
        model=editor_model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 5}),
            tools=CombinedToolSet(note_reader.as_tool(), ReadNote()),
            events=TranscriptBus(label="editor"),
        ),
        initial=InitialState(system="Write short digests. Delegate the reading."),
    )

    print(editor.tree())
    outcome = await editor.agent().run("Write a digest of my ideas.")
    print(message_text(outcome.final))
    # --8<-- [end:blueprint]


asyncio.run(main())
