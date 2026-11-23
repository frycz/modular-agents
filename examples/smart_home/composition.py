"""The smart home: several devices plus the whole barista agent as one more tool."""

from __future__ import annotations

from examples.coffee_machine import coffee_machine
from examples.smart_home.devices import (
    Blinds,
    FrontDoor,
    Lights,
    Thermostat,
)
from examples.smart_home.playbooks import PLAYBOOKS
from examples.smart_home.prompts import SYSTEM
from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.devices.device import DeviceToolSet
from modular_agents.composites.events.guard_bus import GuardBus, clamp, forbid
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState


def smart_home(name: str = "home", model: Model | None = None) -> Blueprint:
    # each home has its own devices, so two homes are two separate worlds
    devices = DeviceToolSet(Lights("bedroom"), Lights("kitchen"), Blinds(), Thermostat(), FrontDoor())
    barista = coffee_machine(model).as_tool()  # a whole agent, plugged in like a device
    events = GuardBus(
        TranscriptBus(name),
        forbid("front_door_unlock", "only a person with a key may unlock the door"),
        clamp("thermostat_set", "celsius", lo=16, hi=24),
    )
    harness = Harness(StandardLoop(), TreeBudget({"steps": 10}), CombinedToolSet(devices, barista), events=events)
    return Blueprint(
        name, "runs one home: morning and night routines, lights, heating, the door, and coffee.",
        model or PlaybookModel("playbook:home", PLAYBOOKS), harness, InitialState(SYSTEM),
    )
