"""What the playbook model does for each task keyword, when no real model is given."""

from __future__ import annotations

from modular_agents.composites.model.playbook_model import call, say

INSPECTOR_PLAYBOOKS = {
    "inspect": [
        [call("reactor_status"), call("turbine_status"), call("grid_status")],
        say(lambda r: "Gauges: " + "; ".join(r)),
    ],
    "tamper": [  # the inspector's tool view has no set_* tools, so this is an unknown tool, not a denied one
        call("reactor_set_rods", percent=0),
        say(lambda r: f"I cannot do that: {r[-1]}"),
    ],
}

PLAYBOOKS = {
    "ramp": [
        call("inspector", task="Inspect the plant before a power ramp."),
        [call("reactor_set_rods", percent=5), call("turbine_set_valve", percent=95)],  # rods too far out: the guard says no
        call("grid_status"),
        say(lambda r: f"Ramped up for the peak. {r[-1]}."),
    ],
    "lower": [
        [call("reactor_set_rods", percent=60), call("turbine_set_valve", percent=70)],
        say(lambda r: f"Output lowered for the night: {r[-1]}."),
    ],
    "scram": [
        [call("reactor_set_rods", percent=100), call("turbine_set_valve", percent=0)],
        say("Reactor scrammed, turbine stopped."),
    ],
}
