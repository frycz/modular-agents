"""The plant's devices: reactor, turbine and grid, wired to each other."""

from __future__ import annotations

from modular_agents.composites.devices.device import Device, action


class Reactor(Device):
    name = "reactor"
    description = "the reactor, power falls as control rods go in"

    def __init__(self):
        self.rods_pct = 50  # 100 = fully inserted, shut down

    @property
    def thermal_mw(self) -> float:
        return (100 - self.rods_pct) * 12.5

    @action(readonly=True)
    def status(self) -> str:
        """Report the current state."""
        return f"rods {self.rods_pct}% in, {self.thermal_mw:g} MW thermal"

    @action
    def set_rods(self, percent: int) -> str:
        """Insert the control rods to a percentage, 100 shuts the reactor down."""
        self.rods_pct = percent
        return f"rods at {percent}%, {self.thermal_mw:g} MW thermal"


class Turbine(Device):
    name = "turbine"
    description = "the steam turbine, turns reactor heat into electricity"

    def __init__(self, reactor: Reactor):
        self._reactor = reactor
        self.valve_pct = 80

    @property
    def output_mw(self) -> float:
        return self._reactor.thermal_mw * self.valve_pct / 100

    @action(readonly=True)
    def status(self) -> str:
        """Report the current state."""
        return f"valve {self.valve_pct}% open, {self.output_mw:g} MW out"

    @action
    def set_valve(self, percent: int) -> str:
        """Open the steam valve to a percentage."""
        self.valve_pct = percent
        return f"valve at {percent}%, {self.output_mw:g} MW out"


class Grid(Device):
    name = "grid"
    description = "the city grid connection"

    def __init__(self, turbine: Turbine, demand_mw: float = 900):
        self._turbine = turbine
        self.demand_mw = demand_mw

    @action(readonly=True)
    def status(self) -> str:
        """Report the current state."""
        balance = self._turbine.output_mw - self.demand_mw
        return f"demand {self.demand_mw:g} MW, supplied {self._turbine.output_mw:g} MW, balance {balance:+g} MW"
