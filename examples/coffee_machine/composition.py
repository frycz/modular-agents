"""The barista: one device, a guard that protects the boiler. The smallest toy, and a building block of the smart home."""

from __future__ import annotations

from examples.coffee_machine.devices import CoffeeMachine
from examples.coffee_machine.playbooks import PLAYBOOKS
from examples.coffee_machine.prompts import SYSTEM
from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.devices.device import DeviceToolSet
from modular_agents.composites.events.guard_bus import GuardBus, clamp
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState


def coffee_machine(model: Model | None = None, machine: CoffeeMachine | None = None) -> Blueprint:
    machine = machine or CoffeeMachine()
    events = GuardBus(TranscriptBus("barista"), clamp("coffee_heat", "celsius", hi=96))
    harness = Harness(StandardLoop(), TreeBudget({"steps": 6}), DeviceToolSet(machine), events=events)
    return Blueprint(
        "barista", "makes coffee drinks (espresso, latte) on the espresso machine.",
        model or PlaybookModel("playbook:barista", PLAYBOOKS), harness, InitialState(SYSTEM),
    )
