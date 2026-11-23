"""Model access layer, public side: what the rest of the system sees."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict

from .cancellation import AbortSignal
from .lifecycle import Resource
from .messages import ContentBlock, Ext, Message, TextBlock

type ModelRef = str
type System = str | list[TextBlock]  # blocks let parts of the system prompt carry ext, e.g. a cache breakpoint


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict
    ext: NotRequired[Ext]  # provider data; an ext with a "type" is a provider-side tool (e.g. web search), sent as is


type StopReason = Literal["end_turn", "tool_use", "max_tokens", "pause_turn", "refusal"]


class Usage(TypedDict):
    input_tokens: int  # not read from or written to the cache
    output_tokens: int
    cost_usd: float
    elapsed_ms: float
    cache_read_tokens: NotRequired[int]
    cache_write_tokens: NotRequired[int]


class ModelParams(TypedDict, total=False):
    max_tokens: int
    effort: str  # "low" | "medium" | "high" | ...


@dataclass
class Prompt:
    """What one model call is asked. Built by the loop from the state and the tools, then adjusted by the context policy."""

    system: System
    messages: list[Message]
    tools: list[ToolDefinition] = field(default_factory=list)


@dataclass
class ModelRequest:
    model: ModelRef
    system: System
    messages: list[Message]
    tools: list[ToolDefinition]
    params: ModelParams = field(default_factory=dict)


@dataclass
class ModelResponse:
    content: list[ContentBlock]
    stop_reason: StopReason
    usage: Usage


class TextDeltaEvent(TypedDict):
    type: Literal["text_delta"]
    text: str


class ThinkingDeltaEvent(TypedDict):
    type: Literal["thinking_delta"]
    text: str


class ToolCallStartEvent(TypedDict):
    type: Literal["tool_call_start"]
    id: str
    name: str


class ToolInputDeltaEvent(TypedDict):
    type: Literal["tool_input_delta"]
    id: str
    partial_json: str


class ResponseCompleteEvent(TypedDict):
    type: Literal["response_complete"]
    response: ModelResponse


type DeltaEvent = TextDeltaEvent | ThinkingDeltaEvent | ToolCallStartEvent | ToolInputDeltaEvent
type ModelEvent = DeltaEvent | ResponseCompleteEvent  # a stream always ends with response_complete


@dataclass
class Capabilities:
    context_window: int = 200_000
    tool_calling: bool = True
    parallel_tool_calls: bool = True
    thinking: bool = False
    image_input: bool = False
    structured_output: bool = False
    prompt_caching: bool = False


class Model(Resource, ABC):
    """One model, ready to be requested: one model name on one endpoint, with its params."""

    @property
    @abstractmethod
    def ref(self) -> ModelRef: ...

    @abstractmethod
    async def complete(self, prompt: Prompt, signal: AbortSignal) -> ModelResponse: ...

    @abstractmethod
    def stream(self, prompt: Prompt, signal: AbortSignal) -> AsyncIterator[ModelEvent]: ...

    @abstractmethod
    def capabilities(self) -> Capabilities: ...
