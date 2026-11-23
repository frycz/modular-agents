"""Model access layer internals: one reachable model service, made of a protocol adapter and a transport."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .cancellation import AbortSignal
from .lifecycle import Resource
from .model import Capabilities, ModelEvent, ModelRequest, ModelResponse, Usage

type WireRequest = dict  # protocol-specific JSON
type WireResponse = dict
type WireChunk = dict


class RetryableError(Exception):
    """A transient infrastructure failure (rate limit, overload, network) that may be retried."""


class Endpoint(Resource, ABC):
    """A reachable model service: one protocol, one transport, its own cost model."""

    @property
    @abstractmethod
    def id(self) -> str: ...  # the scheduler keys limits on this

    @abstractmethod
    async def complete(self, req: ModelRequest, caps: Capabilities, signal: AbortSignal) -> ModelResponse: ...

    @abstractmethod
    def stream(self, req: ModelRequest, caps: Capabilities, signal: AbortSignal) -> AsyncIterator[ModelEvent]: ...

    @abstractmethod
    def cost(self, usage: Usage) -> float: ...


class ProtocolAdapter(ABC):
    """Pure data to data: the common representation <-> one protocol's wire format."""

    @abstractmethod
    def encode(self, req: ModelRequest, caps: Capabilities) -> WireRequest: ...

    @abstractmethod
    def decode(self, res: WireResponse) -> ModelResponse: ...

    @abstractmethod
    def decode_stream(self, chunks: AsyncIterator[WireChunk]) -> AsyncIterator[ModelEvent]: ...


class Transport(Resource, ABC):
    @abstractmethod
    async def send(self, req: WireRequest, signal: AbortSignal) -> WireResponse: ...

    @abstractmethod
    def stream(self, req: WireRequest, signal: AbortSignal) -> AsyncIterator[WireChunk]: ...
