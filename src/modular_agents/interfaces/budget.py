"""Budget interface and the budget amounts it works with."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict

from .model import Usage


class BudgetState(TypedDict):
    steps: float
    tokens: float
    cost_usd: float
    elapsed_ms: float


class BudgetLimit(TypedDict, total=False):
    steps: float
    tokens: float
    cost_usd: float
    elapsed_ms: float


class Budget(ABC):
    @abstractmethod
    def remaining(self) -> BudgetState: ...

    @abstractmethod
    def charge(self, usage: Usage) -> None:
        """Also charged to all ancestors."""

    @abstractmethod
    def child(self, limit: BudgetLimit) -> Budget:
        """Capped by the remaining parent budget."""
