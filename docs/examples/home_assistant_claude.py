"""Tutorial: the home assistant on Claude. Requires ANTHROPIC_API_KEY."""

import asyncio

from home_assistant import run_day
from modular_agents.composites.model.anthropic_model import AnthropicModel

haiku = AnthropicModel(ref="claude-haiku-5-5")
asyncio.run(run_day(model=haiku, dj_model=haiku))  # one model object can serve several agents
