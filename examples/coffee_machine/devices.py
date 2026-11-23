"""The espresso machine."""

from __future__ import annotations

from modular_agents.composites.devices.device import Device, action


class CoffeeMachine(Device):
    name = "coffee"
    description = "the kitchen espresso machine"

    def __init__(self):
        self.boiler_c = 20
        self.ground_g = 0
        self.beans_g = 250
        self.milk_ml = 500
        self.cups_made = 0

    @action
    def heat(self, celsius: int) -> str:
        """Heat the boiler to a temperature in °C."""
        self.boiler_c = celsius
        return f"boiler at {celsius}°C"

    @action
    def grind(self, grams: int) -> str:
        """Grind coffee beans."""
        if grams > self.beans_g:
            raise ValueError(f"only {self.beans_g}g of beans left")
        self.beans_g -= grams
        self.ground_g += grams
        return f"ground {grams}g, {self.beans_g}g of beans left"

    @action
    def brew(self, ml: int) -> str:
        """Brew a shot from the ground coffee."""
        if self.boiler_c < 88:
            raise ValueError(f"boiler too cold ({self.boiler_c}°C), heat it to 88-96°C first")
        if not self.ground_g:
            raise ValueError("nothing ground, grind first")
        self.ground_g = 0
        self.cups_made += 1
        return f"brewed {ml}ml at {self.boiler_c}°C (cup #{self.cups_made})"

    @action
    def froth(self, ml: int) -> str:
        """Froth milk."""
        if ml > self.milk_ml:
            raise ValueError(f"only {self.milk_ml}ml of milk left")
        self.milk_ml -= ml
        return f"frothed {ml}ml of milk"
