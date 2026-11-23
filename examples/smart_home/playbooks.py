"""What the playbook model does for each task keyword, when no real model is given."""

from __future__ import annotations

from modular_agents.composites.model.playbook_model import call, say

PLAYBOOKS = {
    "morning": [
        [
            call("bedroom_lights_set", level_pct=60), call("kitchen_lights_set", level_pct=100),
            call("blinds_open", percent=100), call("thermostat_set", celsius=30.0),  # too warm: the guard turns it down
            call("barista", task="Make a latte."),
        ],
        say(lambda r: f"Good morning! Lights on, blinds open, heating set. Barista: {r[-1]}"),
    ],
    "night": [
        [
            call("bedroom_lights_set", level_pct=0), call("kitchen_lights_set", level_pct=0),
            call("blinds_open", percent=0), call("thermostat_set", celsius=18.0), call("front_door_lock"),
        ],
        say("Good night: lights off, blinds closed, heating at 18°C, door locked."),
    ],
    "guest": [
        call("front_door_unlock"),  # the guard denies it, the model has to cope
        say(lambda r: f"I could not let the guest in ({r[-1]}), please open the door yourself."),
    ],
}
