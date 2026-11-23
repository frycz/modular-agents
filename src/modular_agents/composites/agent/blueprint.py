"""Blueprint: everything an agent is made of, so the same agent can run on its own or serve as another agent's tool."""

from __future__ import annotations

from dataclasses import dataclass, field

from modular_agents.composites.events.transcript_bus import path
from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.tools.spawn_agent import SpawnAgentTool
from modular_agents.interfaces.agent import Agent
from modular_agents.interfaces.budget import Budget
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model, ToolDefinition
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import ToolContext, ToolOutput


@dataclass
class Blueprint:
    name: str
    description: str
    model: Model
    harness: Harness
    initial: InitialState = field(default_factory=InitialState)

    def agent(self, session_budget: Budget | None = None) -> Agent:
        """A standalone agent, owning one context across runs."""
        return ComposedAgent(self.model, self.harness, self.initial, session_budget)

    def as_tool(self, name: str | None = None) -> AgentTool:
        """The same agent as a tool: every call is a fresh context, charged to the caller's budget."""
        return AgentTool(self, name or self.name)

    def tree(self) -> str:
        """The composition as a tree: harness parts, plain tools, and agent tools expanded recursively."""
        h = self.harness
        parts = [type(h.loop).__name__, f"budget {_limits(h.budget)}"]
        parts += [_describe(p) for p in (h.policy, h.events, h.store) if p]
        lines = [f"{self.name} [{self.model.ref}]: {self.description}", f"  harness: {', '.join(parts)}"]
        tools = [h.tools.get(d["name"]) for d in h.tools.definitions()] if h.tools else []
        plain = [t.definition["name"] for t in tools if not isinstance(t, AgentTool)]
        agents = [t for t in tools if isinstance(t, AgentTool)]
        if plain:
            lines.append(f"  tools: {', '.join(plain)}")
        for i, t in enumerate(agents):
            first, rest = ("└─ ", "   ") if i == len(agents) - 1 else ("├─ ", "│  ")
            sub = t.blueprint.tree().splitlines()
            sub[0] = f"{t.definition['name']} = {sub[0]}" if t.definition["name"] != t.blueprint.name else sub[0]
            lines += [f"  {first}{sub[0]}"] + [f"  {rest}{s}" for s in sub[1:]]
        return "\n".join(lines)


class AgentTool(SpawnAgentTool):
    """Any blueprint as a named tool. From the caller's side it is indistinguishable from a device button."""

    def __init__(self, blueprint: Blueprint, name: str):
        super().__init__(blueprint.model, blueprint.harness, blueprint.initial)
        self.blueprint = blueprint
        self.name = name

    @property
    def definition(self) -> ToolDefinition:
        return {
            **super().definition, "name": self.name,
            "description": f"Delegate a task to the {self.blueprint.name} agent: {self.blueprint.description}",
        }

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        token = path.set(path.get() + (self.name,))  # for the transcript: where in the tree the sub-agent runs
        try:
            return await super().execute(input, ctx)
        finally:
            path.reset(token)


def _limits(budget: Budget) -> str:
    return ", ".join(f"{k}={v:g}" for k, v in budget.remaining().items() if v != float("inf")) or "unlimited"


def _describe(part) -> str:
    """Class names of stacked parts, e.g. GuardBus(TranscriptBus)."""
    inner = getattr(part, "inner", None)
    return f"{type(part).__name__}({_describe(inner)})" if inner else type(part).__name__
