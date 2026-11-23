"""Run state: the context of one run, as plain serializable data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, TypedDict

from .budget import BudgetState
from .messages import Message
from .model import ModelRef, System


class RunMeta(TypedDict):
    model: ModelRef  # which model produced this context


@dataclass
class InitialState:
    """What a new context starts with. Turned into a RunState once, when the agent is created."""

    system: System = ""
    messages: list[Message] = field(default_factory=list)


@dataclass
class RunState:
    system: System
    messages: list[Message]
    budget: BudgetState  # what is left, as of the last step
    meta: RunMeta
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: str | None = None
    context_tokens: int = 0  # size of the context as of the last response, for compaction decisions
    data: dict[str, Any] = field(default_factory=dict)  # owned by tools and policies (todos, permission mode), saved with the run
