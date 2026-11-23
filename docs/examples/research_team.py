"""Tutorial: a research agent and a writer agent that uses it as a tool."""

import asyncio

from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.guard_bus import GuardBus, clamp
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool

# --8<-- [start:tool]
NOTES = [
    "The budget limits steps, tokens, cost and time.",
    "A run stops when the model answers or the budget runs out.",
    "A sub-agent's spending is charged to its parent's budget.",
    "Tool calls can be denied or changed by the event bus.",
]


class SearchNotes(Tool):
    readonly = concurrent = True

    def __init__(self, notes: list[str]):
        self.notes = notes

    @property
    def definition(self):
        return {
            "name": "search_notes",
            "description": "Find notes that mention a word. Returns at most `limit` notes.",
            "input_schema": {
                "type": "object",
                "properties": {"word": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["word"],
            },
        }

    async def execute(self, input, ctx=None):
        found = [n for n in self.notes if input["word"].lower() in n.lower()][: input.get("limit", 3)]
        return text_output(text=" ".join(found) or "no notes found")
# --8<-- [end:tool]


# --8<-- [start:research]
def research_agent(model: Model) -> Blueprint:
    return Blueprint(
        name="research_agent",
        description="searches the notes and reports what they say.",
        model=model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 5}),
            tools=StaticToolSet(tools=[SearchNotes(notes=NOTES)]),
            events=GuardBus(
                TranscriptBus(label="research_agent"),
                clamp(tool="search_notes", field="limit", lo=1, hi=2),
            ),
        ),
        initial=InitialState(system="Search the notes and report what they say about the topic. Quote the notes."),
    )
# --8<-- [end:research]


# --8<-- [start:writer]
def writer_agent(model: Model, research: Blueprint) -> Blueprint:
    return Blueprint(
        name="writer_agent",
        description="writes short summaries.",
        model=model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 10}),
            tools=StaticToolSet(tools=[research.as_tool()]),
            events=TranscriptBus(label="writer_agent"),
        ),
        initial=InitialState(system="Write one-line summaries. Ask the research agent for the facts first."),
    )
# --8<-- [end:writer]


# --8<-- [start:run]
async def run_team(research_model: Model, writer_model: Model, task: str) -> None:
    team = writer_agent(model=writer_model, research=research_agent(model=research_model))
    print(team.tree(), end="\n\n")

    session = TreeBudget(limit={"tokens": 100_000})  # every model call in the tree is charged here
    async with team.agent(session_budget=session) as agent:
        outcome = await agent.run(task)
    print(f"\n{message_text(outcome.final)}")
    print(f"whole team: {session.spent['steps']} model calls, {session.spent['tokens']} tokens")
# --8<-- [end:run]


# --8<-- [start:offline]
research_script = PlaybookModel(ref="playbook:research", playbooks={
    "budget": [call("search_notes", word="budget", limit=10), say(lambda results: results[-1])],
})
writer_script = PlaybookModel(ref="playbook:writer", playbooks={
    "summary": [
        call("research_agent", task="Find what the notes say about the budget."),
        say(lambda results: f"Summary: {results[-1]}"),
    ],
})

if __name__ == "__main__":
    asyncio.run(run_team(research_script, writer_script, "Write a one-line summary of how the budget works."))
# --8<-- [end:offline]
