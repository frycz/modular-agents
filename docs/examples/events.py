"""Events: observing a run, and intercepting tasks and tool calls."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.guard_bus import GuardBus, forbid
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.events import Deny, EventBus, Modify
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.tools import Tool

NOTES = {"groceries": "milk, eggs, coffee"}


class WriteNote(Tool):
    definition = {
        "name": "write_note",
        "description": "Create or replace a note.",
        "input_schema": schema(title="The title of the note.", text="The full text of the note."),
    }

    async def execute(self, input, ctx=None):
        NOTES[input["title"]] = input["text"]
        return text_output(text=f"saved {input['title']}")


class DeleteNote(Tool):
    definition = {
        "name": "delete_note",
        "description": "Delete a note.",
        "input_schema": schema(title="The title of the note."),
    }

    async def execute(self, input, ctx=None):
        NOTES.pop(input["title"], None)
        return text_output(text=f"deleted {input['title']}")


# --8<-- [start:bus]
class AuditBus(EventBus):
    """Prints every tool call and result, refuses tasks that mention passwords, and lower-cases note titles."""

    def emit(self, e):
        if e["type"] == "tool_call":
            print(f"  call    {e['name']}({e['input']})")
        elif e["type"] == "tool_result":
            print(f"  result  {e['content'][0]['text']} (error: {e['is_error']})")

    async def intercept(self, e):
        if e["type"] == "prompt" and "password" in str(e["content"]).lower():
            return Deny("tasks about passwords are not accepted")
        if e["type"] == "tool_call" and "title" in e["input"]:
            return Modify({**e["input"], "title": e["input"]["title"].lower()})
        return "allow"
# --8<-- [end:bus]


model = PlaybookModel(ref="playbook:notes", playbooks={
    "trip": [call("write_note", title="Trip", text="book the train"), say(lambda results: results[-1])],
    "password": [say("(never reached)")],
    "clean": [call("delete_note", title="groceries"), say(lambda results: results[-1])],
    "long": [call("write_note", title="essay", text="word " * 50), say(lambda results: results[-1])],
})
tools = StaticToolSet(tools=[WriteNote(), DeleteNote()])


async def main():
    # --8<-- [start:run_bus]
    agent = ComposedAgent(
        model=model,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 5}), tools=tools, events=AuditBus()),
    )
    for task in ["Note the trip.", "Store my password."]:
        print(task)
        outcome = await agent.run(task)
        print(f"  -> {outcome.reason}: {message_text(outcome.final)}")
    print(sorted(NOTES))
    # --8<-- [end:run_bus]

    # --8<-- [start:guard]
    def short_notes(e):
        """A custom rule: None means no objection."""
        if e["name"] == "write_note" and len(e["input"]["text"]) > 100:
            return Deny("notes are limited to 100 characters"), "write_note denied, the note is too long"
        return None

    guard = GuardBus(
        TranscriptBus(label="notes_agent"),
        forbid(tool="delete_note", reason="notes are never deleted"),
        short_notes,
    )
    agent = ComposedAgent(
        model=model,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 5}), tools=tools, events=guard),
    )
    await agent.run("Clean up the groceries note.")
    await agent.run("Write a long essay.")
    # --8<-- [end:guard]


asyncio.run(main())
