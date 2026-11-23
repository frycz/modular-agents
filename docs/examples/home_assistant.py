"""Tutorial: a home assistant with its own tools, context policy, event bus and a DJ agent as a tool."""

import asyncio
import json
from dataclasses import dataclass, field, replace
from datetime import datetime

from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.events import Deny, EventBus
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.state import InitialState
from modular_agents.interfaces.tools import Tool


# --8<-- [start:home]
@dataclass
class Home:
    """A simulated home: the state that the tools, the policy and the event bus share."""

    now: datetime
    lights: dict[str, bool] = field(default_factory=lambda: {"kitchen": False, "living room": False, "bedroom": False})
    song: str | None = None
    temperature: dict[str, int] = field(default_factory=lambda: {"inside": 19, "outside": 4})
    forecast: dict[str, str] = field(default_factory=lambda: {
        "today": "cloudy, rain from 14:00 to 18:00, high 8°C",
        "tomorrow": "sunny, high 11°C",
    })
# --8<-- [end:home]


# --8<-- [start:prompts]
ASSISTANT_PROMPT = """\
You are a home assistant. You control the lights and the music and you report the temperature and the weather.
The home has three rooms: kitchen, living room and bedroom. The current time and the state of the home are given below.
To play music you need a song name. If the resident describes a mood instead of a song, ask pick_song first.
When the resident says good morning: read both temperatures and today's forecast, turn on the kitchen lights,
play a calm morning song, and answer with a short briefing.
Answer in one to three short sentences. If a tool call is denied, tell the resident why."""

DJ_PROMPT = """\
You pick songs for a home music player. Pick one well-known song that fits the request.
Answer with the song name and the artist only, for example: "Clair de Lune" by Debussy."""
# --8<-- [end:prompts]


# --8<-- [start:tools]
ROOM = {"type": "string", "enum": ["kitchen", "living room", "bedroom"]}


def object_schema(**properties):
    return {"type": "object", "properties": properties, "required": list(properties)}


class HomeTool(Tool):
    def __init__(self, home: Home):
        self.home = home


class LightsOn(HomeTool):
    definition = {"name": "lights_on", "description": "Turn on the lights in one room.", "input_schema": object_schema(room=ROOM)}

    async def execute(self, input, ctx=None):
        self.home.lights[input["room"]] = True
        return text_output(text=f"The {input['room']} lights are on.")


class LightsOff(HomeTool):
    definition = {"name": "lights_off", "description": "Turn off the lights in one room.", "input_schema": object_schema(room=ROOM)}

    async def execute(self, input, ctx=None):
        self.home.lights[input["room"]] = False
        return text_output(text=f"The {input['room']} lights are off.")


class PlayMusic(HomeTool):
    definition = {
        "name": "play_music",
        "description": "Play a song by its name.",
        "input_schema": object_schema(song={"type": "string"}),
    }

    async def execute(self, input, ctx=None):
        self.home.song = input["song"]
        return text_output(text=f"Playing {input['song']}.")


class StopMusic(HomeTool):
    definition = {"name": "stop_music", "description": "Stop the music.", "input_schema": object_schema()}

    async def execute(self, input, ctx=None):
        if self.home.song is None:
            return text_output(text="No music is playing.")
        self.home.song = None
        return text_output(text="The music is stopped.")


class GetTemperature(HomeTool):
    readonly = concurrent = True
    definition = {
        "name": "get_temperature",
        "description": "Read the temperature inside or outside the home, in °C.",
        "input_schema": object_schema(where={"type": "string", "enum": ["inside", "outside"]}),
    }

    async def execute(self, input, ctx=None):
        return text_output(text=f"{self.home.temperature[input['where']]}°C")


class GetForecast(HomeTool):
    readonly = concurrent = True
    definition = {
        "name": "get_forecast",
        "description": "Get the weather forecast for today or tomorrow.",
        "input_schema": object_schema(day={"type": "string", "enum": ["today", "tomorrow"]}),
    }

    async def execute(self, input, ctx=None):
        return text_output(text=self.home.forecast[input["day"]])


def home_tools(home: Home) -> StaticToolSet:
    return StaticToolSet(tools=[
        LightsOn(home), LightsOff(home), PlayMusic(home), StopMusic(home), GetTemperature(home), GetForecast(home),
    ])
# --8<-- [end:tools]


# --8<-- [start:policy]
class HomeStatusPolicy(ContextPolicy):
    """Adds the time and the state of the home to the system prompt of every call."""

    def __init__(self, home: Home):
        self.home = home

    async def prepare(self, state, prompt, model):
        lights = [room for room, on in self.home.lights.items() if on]
        status = (
            f"Time: {self.home.now:%A %H:%M}\n"
            f"Lights on: {', '.join(lights) or 'none'}\n"
            f"Music: {self.home.song or 'not playing'}"
        )
        return replace(prompt, system=f"{prompt.system}\n\n{status}")
# --8<-- [end:policy]


# --8<-- [start:events]
class HomeEvents(EventBus):
    """Logs every tool call and result, and keeps the quiet hours from 22:00 to 07:00."""

    def __init__(self, home: Home):
        self.home = home

    def log(self, kind, text):
        print(f"{self.home.now:%H:%M}  {kind:<9}  {text}")

    def emit(self, e):
        if e["type"] == "tool_call":
            args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in e["input"].items())
            self.log("tool", f"{e['name']}({args})")
        elif e["type"] == "tool_result":
            self.log("result", e["content"][0]["text"])

    async def intercept(self, e):
        hour = self.home.now.hour
        if e["type"] == "tool_call" and e["name"] == "play_music" and (hour >= 22 or hour < 7):
            return Deny("quiet hours, 22:00 to 07:00")
        return "allow"
# --8<-- [end:events]


# --8<-- [start:compose]
def home_assistant(home: Home, model: Model, dj_model: Model) -> Blueprint:
    dj = Blueprint(
        name="pick_song",
        description="picks a song that fits a mood or an occasion, and returns its name and artist.",
        model=dj_model,
        harness=Harness(loop=StandardLoop(), budget=TreeBudget(limit={"steps": 1})),
        initial=InitialState(system=DJ_PROMPT),
    )
    return Blueprint(
        name="home_assistant",
        description="controls the lights and the music, and reports the temperature and the weather.",
        model=model,
        harness=Harness(
            loop=StandardLoop(),
            budget=TreeBudget(limit={"steps": 8}),
            tools=CombinedToolSet(home_tools(home), dj.as_tool()),
            policy=HomeStatusPolicy(home),
            events=HomeEvents(home),
        ),
        initial=InitialState(system=ASSISTANT_PROMPT),
    )
# --8<-- [end:compose]


# --8<-- [start:day]
DAY = [
    ("07:15", "Good morning."),
    ("13:20", "Should I open the window?"),
    ("19:30", "Turn on the living room lights and play something calm."),
    ("21:05", "Turn off all the lights and stop the music."),
    ("23:10", 'Play "Thunderstruck".'),
]


async def run_day(model: Model, dj_model: Model) -> None:
    home = Home(now=datetime(2026, 11, 23, 7, 15))
    assistant = home_assistant(home=home, model=model, dj_model=dj_model)
    for time, request in DAY:
        hour, minute = map(int, time.split(":"))
        home.now = home.now.replace(hour=hour, minute=minute)
        print(f"{time}  user       {request}")
        outcome = await assistant.agent().run(request)  # a new agent per request: a fresh conversation
        print(f"{time}  assistant  {message_text(outcome.final)}\n")
# --8<-- [end:day]


# --8<-- [start:offline]
assistant_script = PlaybookModel(ref="playbook:home", playbooks={
    "good morning": [
        [call("get_temperature", where="inside"), call("get_temperature", where="outside"), call("get_forecast", day="today")],
        [call("lights_on", room="kitchen"), call("pick_song", task="a calm song for the morning")],
        call("play_music", song="Here Comes the Sun"),
        say(lambda r: f"Good morning. It is {r[0]} inside and {r[1]} outside. Today: {r[2]}. "
                      f"The kitchen lights are on and {r[4]} is playing."),
    ],
    "window": [
        [call("get_temperature", where="inside"), call("get_temperature", where="outside"), call("get_forecast", day="today")],
        say(lambda r: f"It is {r[0]} inside and {r[1]} outside. Today: {r[2]}. Better keep it closed."),
    ],
    "calm": [
        [call("lights_on", room="living room"), call("pick_song", task="something calm for the evening")],
        call("play_music", song="Clair de Lune"),
        say(lambda r: f"The living room lights are on and {r[1]} is playing."),
    ],
    "turn off all": [
        [call("lights_off", room=room) for room in ("kitchen", "living room", "bedroom")] + [call("stop_music")],
        say("All the lights are off and the music is stopped."),
    ],
    "thunderstruck": [
        call("play_music", song="Thunderstruck"),
        say(lambda r: f"I cannot play music now: {r[-1].split(': ', 1)[-1]}."),
    ],
})
dj_script = PlaybookModel(ref="playbook:dj", playbooks={
    "morning": [say('"Here Comes the Sun" by The Beatles')],
    "calm": [say('"Clair de Lune" by Debussy')],
})

if __name__ == "__main__":
    asyncio.run(run_day(model=assistant_script, dj_model=dj_script))
# --8<-- [end:offline]
