"""The loop used directly: a run state, a run context and one step at a time."""

import asyncio

from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import schema, text_output
from modular_agents.interfaces.loop import RunContext
from modular_agents.interfaces.state import RunState
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


model = PlaybookModel(ref="playbook:notes", playbooks={
    "groceries": [call("read_note", title="groceries"), say(lambda results: f"Buy {results[-1]}.")],
})


def describe(message):
    parts = []
    for b in message["content"]:
        match b["type"]:
            case "text":
                parts.append(f"text {b['text']!r}")
            case "tool_call":
                parts.append(f"tool_call {b['name']}({b['input']})")
            case "tool_result":
                parts.append(f"tool_result {b['content'][0]['text']!r}")
    return f"{message['role']}: {', '.join(parts)}"


async def main():
    # --8<-- [start:setup]
    budget = TreeBudget(limit={"steps": 5})
    state = RunState(
        system="You manage notes.",
        messages=[{"role": "user", "content": [{"type": "text", "text": "What is on the groceries list?"}]}],
        budget=budget.remaining(),
        meta={"model": model.ref},
    )
    ctx = RunContext(
        model=model,
        budget=budget,
        signal=asyncio.Event(),  # set it to cancel the run
        tools=StaticToolSet(tools=[ReadNote()]),
    )
    # --8<-- [end:setup]

    # --8<-- [start:steps]
    loop = StandardLoop()
    step = 1
    while (outcome := await loop.step(state, ctx)) is None:
        print(f"after step {step}: {len(state.messages)} messages")
        step += 1
    print(f"stopped: {outcome.reason}\n")
    for message in state.messages:
        print(describe(message))
    # --8<-- [end:steps]


asyncio.run(main())
