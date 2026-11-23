"""The first agent on Claude. Requires ANTHROPIC_API_KEY."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.anthropic_model import AnthropicModel
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool

FORECASTS = {"oslo": "snow, -3°C", "lisbon": "sunny, 19°C"}


class GetForecast(Tool):
    readonly = concurrent = True  # only reads, so several calls may run in parallel

    @property
    def definition(self):
        return {
            "name": "get_forecast",
            "description": "Get today's weather forecast for a city.",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }

    async def execute(self, input, ctx=None):
        forecast = FORECASTS.get(input["city"].lower())
        if forecast is None:
            return text_output(text=f"no forecast for {input['city']}", is_error=True)
        return text_output(text=forecast)


# --8<-- [start:model]
model = AnthropicModel(ref="claude-haiku-5-5")  # the API key is read from ANTHROPIC_API_KEY
# --8<-- [end:model]

agent = ComposedAgent(
    model=model,
    harness=Harness(
        loop=StandardLoop(),
        budget=TreeBudget(limit={"steps": 5}),
        tools=StaticToolSet(tools=[GetForecast()]),
        events=TranscriptBus(label="weather_agent"),
    ),
    initial_state=InitialState(system="Answer questions about the weather. Use get_forecast."),
)


async def main():
    async with agent:
        outcome = await agent.run("What is the weather in Oslo and Lisbon?")
    print(outcome.reason)
    print(message_text(outcome.final))


asyncio.run(main())
