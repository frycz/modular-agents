"""Tools and tool sets over a small in-memory notebook."""

import asyncio

from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.tools import Tool

# --8<-- [start:tools]
NOTES = {"groceries": "milk, eggs, coffee", "ideas": "give every sub-agent its own budget"}


class ListNotes(Tool):
    readonly = concurrent = True
    definition = {
        "name": "list_notes",
        "description": "List the titles of all notes.",
        "input_schema": {"type": "object", "properties": {}},
    }

    async def execute(self, input, ctx=None):
        return text_output(text=", ".join(sorted(NOTES)))


class ReadNote(Tool):
    readonly = concurrent = True
    definition = {
        "name": "read_note",
        "description": "Read one note by its title.",
        "input_schema": schema(title="The title of the note."),
    }

    async def execute(self, input, ctx=None):
        if input["title"] not in NOTES:
            return text_output(text=f"there is no note titled {input['title']}", is_error=True)
        return text_output(text=NOTES[input["title"]])


class WriteNote(Tool):
    # changes the notebook: not readonly, and never run in parallel with other calls
    definition = {
        "name": "write_note",
        "description": "Create or replace a note.",
        "input_schema": schema(title="The title of the note.", text="The full text of the note."),
    }

    async def execute(self, input, ctx=None):
        NOTES[input["title"]] = input["text"]
        return text_output(text=f"saved {input['title']}")
# --8<-- [end:tools]


async def main():
    # --8<-- [start:sets]
    reading = StaticToolSet(tools=[ListNotes(), ReadNote()])
    everything = CombinedToolSet(reading, WriteNote())  # tool sets and single tools, joined

    print([d["name"] for d in reading.definitions()])
    print([d["name"] for d in everything.definitions()])
    # --8<-- [end:sets]

    # --8<-- [start:direct]
    # A tool can be called without a model or a loop: ctx is then None.
    tool = everything.get("read_note")
    print(await tool.execute({"title": "groceries"}))
    print(await tool.execute({"title": "diary"}))
    # --8<-- [end:direct]


asyncio.run(main())
