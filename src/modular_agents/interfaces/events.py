"""Events interface: observation (emit) and interception are separate.

Interception points and what a decision means at each:
- prompt: a task is about to be added to the context. Deny blocks the run, Modify replaces the content.
- tool_call: before a tool runs. Deny answers the call with an error, Modify replaces the input.
- tool_result: after a tool ran. Deny replaces the result with an error, Modify replaces the content.
- stop: the model ended its turn. Deny keeps the run going, the reason is given to the model as the next message.
- compact: the policy is about to compact the context. Deny skips it.
A deny's reason is shown to the model (or to the user, for prompt).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from .messages import ContentBlock
from .model import DeltaEvent, StopReason, Usage


class PromptEvent(TypedDict):
    type: Literal["prompt"]
    run_id: str
    content: list[ContentBlock]


class RequestEvent(TypedDict):
    type: Literal["request"]
    run_id: str
    messages: int


class StreamEvent(TypedDict):
    type: Literal["delta"]
    run_id: str
    delta: DeltaEvent  # text, thinking and tool input as the model produces them, for UIs


class ResponseEvent(TypedDict):
    type: Literal["response"]
    run_id: str
    stop_reason: StopReason
    usage: Usage


class ToolCallEvent(TypedDict):
    type: Literal["tool_call"]
    run_id: str
    call_id: str
    name: str
    input: Any


class ToolResultEvent(TypedDict):
    type: Literal["tool_result"]
    run_id: str
    call_id: str
    name: str
    is_error: bool
    content: list[ContentBlock]


class StopEvent(TypedDict):
    type: Literal["stop"]
    run_id: str


class CompactEvent(TypedDict):
    type: Literal["compact"]
    run_id: str
    messages: int


class DoneEvent(TypedDict):
    type: Literal["done"]
    run_id: str
    reason: str


type LoopEvent = (
    PromptEvent | RequestEvent | StreamEvent | ResponseEvent | ToolCallEvent | ToolResultEvent | StopEvent | CompactEvent | DoneEvent
)
type InterceptableEvent = PromptEvent | ToolCallEvent | ToolResultEvent | StopEvent | CompactEvent


@dataclass
class Deny:
    reason: str = ""


@dataclass
class Modify:
    value: Any  # prompt: the content; tool_call: the input; tool_result: the content


type Decision = Literal["allow"] | Deny | Modify


class EventBus(ABC):
    @abstractmethod
    def emit(self, e: LoopEvent) -> None:
        """Observation: logging, tracing, UI."""

    @abstractmethod
    async def intercept(self, e: InterceptableEvent) -> Decision:
        """Permissions, approval, hooks."""
