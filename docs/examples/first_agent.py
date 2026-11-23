"""A first agent: one tool, a harness and a scripted model. Runs offline."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool

# --8<-- [start:tool]
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
# --8<-- [end:tool]


# --8<-- [start:model]
model = PlaybookModel(ref="playbook:weather", playbooks={
    "weather": [
        [call("get_forecast", city="Oslo"), call("get_forecast", city="Lisbon")],
        say(lambda results: f"Oslo: {results[0]}. Lisbon: {results[1]}."),
    ],
})
# --8<-- [end:model]

# --8<-- [start:agent]
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
# --8<-- [end:agent]


# --8<-- [start:run]
async def main():
    async with agent:
        outcome = await agent.run("What is the weather in Oslo and Lisbon?")
    print(outcome.reason)
    print(message_text(outcome.final))


asyncio.run(main())
# --8<-- [end:run]
