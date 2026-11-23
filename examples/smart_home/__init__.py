"""The smart home: several devices plus the whole barista agent as one more tool."""

from __future__ import annotations

from examples.smart_home.composition import smart_home
from examples.smart_home.devices import (
    Blinds,
    FrontDoor,
    Lights,
    Thermostat,
)

__all__ = ["Blinds", "FrontDoor", "Lights", "Thermostat", "smart_home"]
