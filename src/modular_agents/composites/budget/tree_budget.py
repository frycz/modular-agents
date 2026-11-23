"""TreeBudget: a budget whose spend is also charged to its ancestors."""

from __future__ import annotations

from modular_agents.interfaces.budget import Budget, BudgetLimit, BudgetState
from modular_agents.interfaces.model import Usage

KEYS = ("steps", "tokens", "cost_usd", "elapsed_ms")


class TreeBudget(Budget):
    def __init__(self, limit: BudgetLimit, parent: Budget | None = None):
        self.limit = {k: limit.get(k, float("inf")) for k in KEYS}  # a missing limit means unlimited
        self.spent = dict.fromkeys(KEYS, 0)
        self.parent = parent

    def remaining(self) -> BudgetState:
        left = {k: self.limit[k] - self.spent[k] for k in KEYS}
        if self.parent:  # never more than the parent has left
            parent_left = self.parent.remaining()
            left = {k: min(left[k], parent_left[k]) for k in KEYS}
        return left

    def charge(self, usage: Usage) -> None:
        self.spent["steps"] += 1
        self.spent["tokens"] += (
            usage["input_tokens"] + usage["output_tokens"] + usage.get("cache_read_tokens", 0) + usage.get("cache_write_tokens", 0)
        )
        self.spent["cost_usd"] += usage["cost_usd"]
        self.spent["elapsed_ms"] += usage["elapsed_ms"]
        if self.parent:
            self.parent.charge(usage)

    def child(self, limit: BudgetLimit) -> Budget:
        return TreeBudget(limit, parent=self)
