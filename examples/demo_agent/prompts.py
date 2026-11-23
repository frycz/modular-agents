"""System prompts of the demo agent and its sub-agents."""

from __future__ import annotations

SYSTEM = (
    "You are a helpful agent with shell and file tools. Work in the current directory. "
    "Use spawn_agent for independent subtasks. Keep the final answer short."
)
SUB_AGENT_SYSTEM = "You are a sub-agent. Do the task, then reply with a short final answer."
