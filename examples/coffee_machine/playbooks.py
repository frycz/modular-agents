"""What the playbook model does for each task keyword, when no real model is given."""

from __future__ import annotations

from modular_agents.composites.model.playbook_model import call, say

PLAYBOOKS = {
    "espresso": [
        [call("coffee_heat", celsius=93), call("coffee_grind", grams=18)],
        call("coffee_brew", ml=30),
        say(lambda r: f"Espresso is ready: {r[-1]}."),
    ],
    "latte": [
        [call("coffee_heat", celsius=120), call("coffee_grind", grams=18)],  # too hot: the guard turns it down
        [call("coffee_brew", ml=30), call("coffee_froth", ml=150)],
        say(lambda r: f"Latte is ready: {r[-2]}, {r[-1]}."),
    ],
    "cold": [  # forgets to heat: the device itself refuses, and the model sees the error
        call("coffee_grind", grams=18),
        call("coffee_brew", ml=30),
        call("coffee_heat", celsius=93),
        call("coffee_brew", ml=30),
        say(lambda r: f"Recovered from a cold boiler: {r[-1]}."),
    ],
}
