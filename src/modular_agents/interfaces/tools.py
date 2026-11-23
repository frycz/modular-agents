"""Tools interface: a definition the model sees, plus execute()."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .budget import Budget
from .cancellation import AbortSignal
from .events import EventBus
from .inbox import Inbox
from .lifecycle import Resource
from .messages import ContentBlock
from .model import ToolDefinition
from .state import RunState


@dataclass
class ToolContext:
    signal: AbortSignal
    budget: Budget
    run_id: str
    state: RunState | None = None  # the caller's context; tools may keep their own data in state.data
    events: EventBus | None = None  # to report progress or ask for approval
    inbox: Inbox | None = None  # to deliver results later, e.g. from a background task


@dataclass
class ToolOutput:
    content: list[ContentBlock]
    is_error: bool = False


class Tool(Resource, ABC):
    readonly: bool = False  # only looks, never changes anything: permission rules can allow it freely
    concurrent: bool = False  # may run at the same time as other calls of the same turn

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition: ...

    @abstractmethod
    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        """ctx is None when the tool is called on its own, outside a loop."""


class ToolSet(Resource, ABC):
    @abstractmethod
    def definitions(self) -> list[ToolDefinition]:
        """Asked on every step, so the set may change during a run (e.g. an MCP server's tool list)."""

    @abstractmethod
    def get(self, name: str) -> Tool | None: ...
