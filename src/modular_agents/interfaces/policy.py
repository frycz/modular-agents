"""Context policy: decides what the model sees of the run state, and when the state itself is compacted."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .budget import Budget
from .cancellation import AbortSignal
from .model import Model, Prompt
from .state import RunState


class ContextPolicy(ABC):
    @abstractmethod
    async def prepare(self, state: RunState, prompt: Prompt, model: Model) -> Prompt:
        """What the model sees on this call: truncation, cache breakpoints, extra system prompt, tool filtering.
        Gets the prompt built from the state and returns a changed copy; never changes the state."""

    def needs_compaction(self, state: RunState, model: Model) -> bool:
        return False

    async def compact(self, state: RunState, model: Model, budget: Budget, signal: AbortSignal) -> None:
        """Rewrite state.messages for good, e.g. replace old history with a summary made by the model.
        Model calls made here are charged to the budget."""
