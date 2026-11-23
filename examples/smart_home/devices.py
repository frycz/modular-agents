"""The home's devices: lights, blinds, thermostat and the front door."""

from __future__ import annotations

from modular_agents.composites.devices.device import Device, action


class Lights(Device):
    def __init__(self, room: str):
        self.name = f"{room}_lights"
        self.description = f"the {room} lights"
        self.level_pct = 0

    @action
    def set(self, level_pct: int) -> str:
        """Dim the lights, 0 is off, 100 is full brightness."""
        self.level_pct = max(0, min(100, level_pct))
        return f"{self.name} at {self.level_pct}%"


class Blinds(Device):
    name = "blinds"
    description = "the living room blinds"

    def __init__(self):
        self.open_pct = 0

    @action
    def open(self, percent: int) -> str:
        """Open the blinds, 0 is closed."""
        self.open_pct = percent
        return f"blinds {percent}% open"


class Thermostat(Device):
    name = "thermostat"
    description = "the central heating"

    def __init__(self):
        self.target_c = 17.0

    @action
    def set(self, celsius: float) -> str:
        """Set the target temperature in °C."""
        self.target_c = celsius
        return f"heating to {celsius}°C"


class FrontDoor(Device):
    name = "front_door"
    description = "the front door lock"

    def __init__(self):
        self.locked = True

    @action
    def lock(self) -> str:
        """Lock the door."""
        self.locked = True
        return "front door locked"

    @action
    def unlock(self) -> str:
        """Unlock the door."""
        self.locked = False
        return "front door unlocked"
