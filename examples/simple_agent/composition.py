"""The simple agent: only the required parts."""

from __future__ import annotations

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.interfaces.agent import Agent
from modular_agents.composites.model.anthropic_model import AnthropicModel


def build_simple_agent(model_name: str, api_key: str | None = None) -> Agent:
    """Only the required parts, everything else left to its default. The API key falls back to ANTHROPIC_API_KEY."""
    return ComposedAgent(AnthropicModel(model_name, api_key))
