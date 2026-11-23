"""The city: no devices at all, only other agents. A power plant and two smart homes, each with its own barista."""

from __future__ import annotations

from examples.city.playbooks import PLAYBOOKS
from examples.city.prompts import SYSTEM
from examples.power_plant import power_plant
from examples.smart_home import smart_home
from modular_agents.composites.agent.blueprint import Blueprint
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.playbook_model import PlaybookModel
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Model
from modular_agents.interfaces.state import InitialState


def city(model: Model | None = None) -> Blueprint:
    tools = CombinedToolSet(power_plant(model).as_tool(), smart_home("home_north", model).as_tool(), smart_home("home_south", model).as_tool())
    harness = Harness(StandardLoop(), TreeBudget({"steps": 30}), tools, events=TranscriptBus("city"))
    return Blueprint(
        "city", "coordinates the power plant and the homes.",
        model or PlaybookModel("playbook:city", PLAYBOOKS), harness, InitialState(SYSTEM),
    )
