"""AdapterEndpoint: an endpoint made of a protocol adapter and a transport."""

from __future__ import annotations

from collections.abc import AsyncIterator

from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.endpoint import Endpoint, ProtocolAdapter, Transport
from modular_agents.interfaces.model import Capabilities, ModelEvent, ModelRequest, ModelResponse, Usage


class AdapterEndpoint(Endpoint):
    def __init__(self, id: str, adapter: ProtocolAdapter, transport: Transport,
                 input_usd_per_mtok: float = 0.0, output_usd_per_mtok: float = 0.0,
                 cache_read_usd_per_mtok: float | None = None, cache_write_usd_per_mtok: float | None = None):
        self._id = id
        self.adapter = adapter
        self.transport = transport
        # cache prices default to Anthropic's ratios to the input price: reads 0.1x, writes 1.25x
        self.prices = (
            input_usd_per_mtok, output_usd_per_mtok,
            input_usd_per_mtok * 0.1 if cache_read_usd_per_mtok is None else cache_read_usd_per_mtok,
            input_usd_per_mtok * 1.25 if cache_write_usd_per_mtok is None else cache_write_usd_per_mtok,
        )

    @property
    def id(self) -> str:
        return self._id

    async def complete(self, req: ModelRequest, caps: Capabilities, signal: AbortSignal) -> ModelResponse:
        return self.adapter.decode(await self.transport.send(self.adapter.encode(req, caps), signal))

    async def stream(self, req: ModelRequest, caps: Capabilities, signal: AbortSignal) -> AsyncIterator[ModelEvent]:
        async for e in self.adapter.decode_stream(self.transport.stream(self.adapter.encode(req, caps), signal)):
            yield e

    def cost(self, usage: Usage) -> float:
        tokens = (usage["input_tokens"], usage["output_tokens"], usage.get("cache_read_tokens", 0), usage.get("cache_write_tokens", 0))
        return sum(t * p for t, p in zip(tokens, self.prices)) / 1_000_000

    async def start(self) -> None:
        await self.transport.start()

    async def aclose(self) -> None:
        await self.transport.aclose()
