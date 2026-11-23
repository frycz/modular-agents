"""Toy agents: the same blueprints run standalone and nested, offline, with playbook models."""

from __future__ import annotations

import asyncio

from examples.city import city
from examples.coffee_machine import CoffeeMachine, coffee_machine
from examples.power_plant import power_plant
from examples.smart_home import smart_home
from modular_agents.composites.agent.blueprint import AgentTool
from modular_agents.composites.devices.device import DeviceToolSet
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text
from modular_agents.interfaces.model import Prompt
from modular_agents.interfaces.tools import ToolContext


def run(blueprint, task, session=None):
    return asyncio.run(blueprint.agent(session).run(task))


def test_device_actions_become_tools():
    machine = CoffeeMachine()
    names = [d["name"] for d in DeviceToolSet(machine).definitions()]
    assert names == ["coffee_brew", "coffee_froth", "coffee_grind", "coffee_heat", "coffee_status"]
    assert [d["name"] for d in DeviceToolSet(machine, readonly=True).definitions()] == ["coffee_status"]
    heat = DeviceToolSet(machine).get("coffee_heat").definition
    assert heat["input_schema"]["properties"] == {"celsius": {"type": "integer"}}


def test_guard_modifies_and_device_errors_reach_the_model():
    machine = CoffeeMachine()
    out = run(coffee_machine(machine=machine), "a latte please")
    assert out.reason == "end_turn"
    assert machine.boiler_c == 96  # asked for 120, clamped by the guard
    assert machine.cups_made == 1 and machine.milk_ml == 350

    machine = CoffeeMachine()
    out = run(coffee_machine(machine=machine), "cold start")
    assert "boiler too cold" in str(out.state.messages)  # the device raised, the loop reported it, the playbook recovered
    assert machine.cups_made == 1


def test_guard_denies():
    out = run(smart_home(), "a guest is at the door")
    assert "denied" in message_text(out.final)


def test_agent_is_a_tool_and_its_spend_goes_to_the_caller():
    session = TreeBudget({})
    out = run(smart_home(), "morning", session)
    assert "Latte is ready" in message_text(out.final)
    assert session.spent["steps"] == 5  # 2 home calls + 3 barista calls


def test_readonly_inspector_cannot_touch():
    plant = power_plant()
    inspector = plant.harness.tools.get("inspector")
    assert isinstance(inspector, AgentTool)
    out = asyncio.run(inspector.execute({"task": "tamper with the rods"}, ToolContext(asyncio.Event(), TreeBudget({}), "test")))
    assert "unknown tool: reactor_set_rods" in message_text({"role": "assistant", "content": out.content})


def test_live_status_is_seen_but_not_stored():
    plant = power_plant()
    out = run(plant, "ramp")
    assert "balance +50 MW" in message_text(out.final)
    assert "[live status]" not in str(out.state.messages)
    seen = asyncio.run(plant.harness.policy.prepare(out.state, Prompt(out.state.system, out.state.messages), plant.model))
    assert "[live status] reactor: rods 20% in" in str(seen.messages[-1])


def test_city_whole_tree():
    session = TreeBudget({})
    out = run(city(), "morning", session)
    assert out.reason == "end_turn"
    text = message_text(out.final)
    assert "balance +50 MW" in text and text.count("Latte is ready") == 2
    assert session.spent["steps"] == 19


def test_parent_budget_caps_the_whole_subtree():
    blueprint = city()
    blueprint.harness.budget = TreeBudget({"steps": 5})
    out = run(blueprint, "morning")
    assert out.reason == "budget_exhausted"
    assert "budget_exhausted" in str(out.state.messages)  # the plant agent stopped too, although its own limit is 10


def test_blocks_recombine():
    """A new agent from existing parts: one coffee machine shared by two baristas, no new classes."""
    machine = CoffeeMachine()
    manager = coffee_machine()
    manager.harness.tools = CombinedToolSet(
        coffee_machine(machine=machine).as_tool("barista_1"), coffee_machine(machine=machine).as_tool("barista_2"),
    )
    manager.harness.budget = TreeBudget({"steps": 20})
    manager.model = PlaybookModel("playbook:manager", {"rush": [  # one after the other: in parallel they would race for the grinds
        call("barista_1", task="espresso"), call("barista_2", task="latte"), say("Two drinks out."),
    ]})
    assert message_text(run(manager, "rush hour").final) == "Two drinks out."
    assert machine.cups_made == 2 and machine.beans_g == 250 - 36
