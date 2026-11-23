"""Toys CLI: print a toy agent's composition tree, then run a task through it."""

from __future__ import annotations

import asyncio
import os
import sys

from examples.city import city
from examples.coffee_machine import coffee_machine
from examples.power_plant import power_plant
from examples.smart_home import smart_home
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.helpers import message_text

TOYS = {"coffee": coffee_machine, "home": smart_home, "plant": power_plant, "city": city}
DEFAULT_TASKS = {
    "coffee": "Make me a latte.",
    "home": "Run the morning routine.",
    "plant": "Ramp up for the morning peak.",
    "city": "Get the city through the morning.",
}


def main() -> None:
    """Usage: uv run python -m examples.toys <coffee|home|plant|city> [task] [--real]

    Without --real every agent follows its playbook offline. With --real all of them share one Claude model,
    read from ANTHROPIC_MODEL and ANTHROPIC_API_KEY.
    """
    args = [a for a in sys.argv[1:] if a != "--real"]
    if not args or args[0] not in TOYS:
        sys.exit(main.__doc__)
    model = None
    if "--real" in sys.argv:
        from modular_agents.composites.model.anthropic_model import AnthropicModel
        model = AnthropicModel(os.environ["ANTHROPIC_MODEL"])
    blueprint = TOYS[args[0]](model=model)
    task = args[1] if len(args) > 1 else DEFAULT_TASKS[args[0]]

    print(blueprint.tree(), end="\n\n")
    print(f"task: {task}\n")
    session = TreeBudget({})  # every model call in the whole tree is charged here
    outcome = asyncio.run(blueprint.agent(session).run(task))
    print(f"\n{message_text(outcome.final)}")
    s = session.spent
    print(f"\nwhole tree spent: {s['steps']} model calls, {s['tokens']} tokens, ${s['cost_usd']:.4f}")


if __name__ == "__main__":
    main()
