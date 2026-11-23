"""A context policy changes what the model sees, never what is stored."""

import asyncio
from dataclasses import replace

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Capabilities, Model, ModelResponse
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.state import InitialState

NOTES = {"groceries": "milk, eggs, coffee", "ideas": "give every sub-agent its own budget"}


# --8<-- [start:policy]
class NoteIndexPolicy(ContextPolicy):
    """Adds the current list of notes to the system prompt of every call."""

    def __init__(self, notes: dict[str, str]):
        self.notes = notes

    async def prepare(self, state, prompt, model):
        index = ", ".join(sorted(self.notes)) or "none"
        return replace(prompt, system=f"{prompt.system}\n\nNotes available: {index}")
# --8<-- [end:policy]


# --8<-- [start:model]
class ShowPromptModel(Model):
    """Prints the system prompt it receives, then answers."""

    ref = "show-prompt"

    async def complete(self, prompt, signal):
        print(f"model sees: {prompt.system!r}")
        usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "elapsed_ms": 0.0}
        return ModelResponse(content=[{"type": "text", "text": "ok"}], stop_reason="end_turn", usage=usage)

    async def stream(self, prompt, signal):
        yield {"type": "response_complete", "response": await self.complete(prompt, signal)}

    def capabilities(self):
        return Capabilities()
# --8<-- [end:model]


async def main():
    # --8<-- [start:run]
    agent = ComposedAgent(
        model=ShowPromptModel(),
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 3}),
            policy=NoteIndexPolicy(notes=NOTES),
        ),
        initial_state=InitialState(system="You manage notes."),
    )
    await agent.run("What notes are there?")
    NOTES["travel"] = "book the train"
    await agent.run("And now?")
    print(f"state keeps: {agent.state.system!r}")
    # --8<-- [end:run]


asyncio.run(main())
