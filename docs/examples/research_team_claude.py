"""Tutorial: the research team on Claude. Requires ANTHROPIC_API_KEY."""

import asyncio

from modular_agents.composites.model.anthropic_model import AnthropicModel
from research_team import run_team

asyncio.run(run_team(
    research_model=AnthropicModel(ref="claude-haiku-5-5"),  # a small, fast model searches
    writer_model=AnthropicModel(ref="claude-sonnet-5-5"),  # a stronger model writes
    task="Write a one-line summary of how the budget works.",
))
