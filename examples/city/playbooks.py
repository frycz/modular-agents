"""What the playbook model does for each task keyword, when no real model is given."""

from __future__ import annotations

from modular_agents.composites.model.playbook_model import call, say

PLAYBOOKS = {
    "morning": [
        call("power_plant", task="The morning peak is coming, ramp up output."),
        [call("home_north", task="Run the morning routine."), call("home_south", task="Run the morning routine.")],
        say(lambda r: f"Morning handled. Plant: {r[0]} North: {r[1]} South: {r[2]}"),
    ],
    "night": [
        [call("home_north", task="Run the night routine."), call("home_south", task="Run the night routine.")],
        call("power_plant", task="Demand is dropping, lower output for the night."),
        say(lambda r: f"City asleep. {r[-1]}"),
    ],
}
