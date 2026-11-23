"""The demo agent: a shell-and-files agent that can spawn sub-agents."""

from __future__ import annotations

from modular_agents.composites.helpers import message_text
from examples.demo_agent.composition import build_agent

__all__ = ["build_agent", "message_text"]
