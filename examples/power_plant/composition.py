"""The power plant: a live status policy, a safety guard, and a read-only inspector sub-agent over the same devices."""

from __future__ import annotations

from examples.power_plant.devices import Grid, Reactor, Turbine
from examples.power_plant.playbooks import INSPECTOR_PLAYBOOKS, PLAYBOOKS
from examples.power_plant.prompts import INSPECTOR_SYSTEM, SYSTEM
from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.devices.device import DeviceToolSet
from modular_agents.composites.events.guard_bus import GuardBus, clamp
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel
from modular_agents.composites.policy.live_status_policy import LiveStatusPolicy
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState


def power_plant(model: Model | None = None, demand_mw: float = 900) -> Blueprint:
    reactor = Reactor()
    turbine = Turbine(reactor)
    grid = Grid(turbine, demand_mw)
    devices = [reactor, turbine, grid]

    # the inspector: same devices, read-only tool view, its own model, prompt and budget
    inspector = Blueprint(
        "inspector", "reads the plant gauges, cannot touch anything.",
        model or PlaybookModel("playbook:inspector", INSPECTOR_PLAYBOOKS),
        Harness(StandardLoop(), TreeBudget({"steps": 3}), DeviceToolSet(*devices, readonly=True), events=TranscriptBus("inspector")),
        InitialState(INSPECTOR_SYSTEM),
    )
    events = GuardBus(TranscriptBus("plant"), clamp("reactor_set_rods", "percent", lo=20, hi=100))
    harness = Harness(
        StandardLoop(), TreeBudget({"steps": 10}), CombinedToolSet(DeviceToolSet(*devices), inspector.as_tool()),
        policy=LiveStatusPolicy(devices), events=events,
    )
    return Blueprint(
        "power_plant", "runs the power plant: ramps output up or down, can scram the reactor.",
        model or PlaybookModel("playbook:plant", PLAYBOOKS), harness, InitialState(SYSTEM),
    )
