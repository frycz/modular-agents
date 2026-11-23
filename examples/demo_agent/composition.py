"""The demo agent: the whole composition in one place."""

from __future__ import annotations

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from examples.demo_agent.events.logging_bus import LoggingEventBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.anthropic_model import AnthropicModel
from examples.demo_agent.policy.truncating_policy import TruncatingContextPolicy
from examples.demo_agent.prompts import SUB_AGENT_SYSTEM, SYSTEM
from examples.demo_agent.store.json_store import JsonRunStore
from examples.demo_agent.tools.env_tools import BashTool, ReadFileTool, WriteFileTool
from modular_agents.composites.tools.spawn_agent import SpawnAgentTool
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.interfaces.agent import Agent
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState


def build_agent(model_name: str, api_key: str, effort: str | None = None) -> Agent:
    # model access layer: AnthropicModel builds its endpoint (adapter + transport) and calls it through a scheduler
    model = AnthropicModel(model_name, api_key, {"effort": effort} if effort else None)

    # parts shared by the main agent and its sub-agents
    events = LoggingEventBus()
    policy = TruncatingContextPolicy()
    store = JsonRunStore()
    bash, read_file, write_file = BashTool(), ReadFileTool(), WriteFileTool()

    # sub-agents: no spawn_agent, so they cannot spawn further agents; the budget is each sub-agent's limit
    sub_harness = Harness(StandardLoop(), TreeBudget({"steps": 10, "tokens": 50_000}), StaticToolSet([bash, read_file, write_file]), policy, events, store)
    spawn_agent = SpawnAgentTool(model, sub_harness, InitialState(SUB_AGENT_SYSTEM))

    # the main agent = model + harness + initial state; the budget is each run's limit
    harness = Harness(StandardLoop(), TreeBudget({"steps": 20, "tokens": 200_000}), StaticToolSet([bash, read_file, write_file, spawn_agent]), policy, events, store)
    return ComposedAgent(model, harness, InitialState(SYSTEM))

