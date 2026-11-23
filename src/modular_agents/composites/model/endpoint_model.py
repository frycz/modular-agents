"""EndpointModel: one model name on one endpoint. Waits for capacity, calls the endpoint, fills in elapsed time and cost."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from modular_agents.composites.model.scheduler import SemaphoreScheduler
from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.endpoint import Endpoint
from modular_agents.interfaces.model import (
    Capabilities,
    Model,
    ModelEvent,
    ModelParams,
    ModelRef,
    ModelRequest,
    ModelResponse,
    Prompt,
)
from modular_agents.interfaces.routing import Scheduler


class EndpointModel(Model):
    def __init__(
        self, endpoint: Endpoint, ref: ModelRef, params: ModelParams | None = None,
        caps: Capabilities | None = None, scheduler: Scheduler | None = None,
    ):
        self.endpoint = endpoint
        self._ref = ref  # the provider's model name, sent as is
        self.params = params or {}
        self.caps = caps or Capabilities()
        self.scheduler = scheduler or SemaphoreScheduler()  # pass the same one to models that share the endpoint's limits

    @property
    def ref(self) -> ModelRef:
        return self._ref

    def capabilities(self) -> Capabilities:
        return self.caps

    async def complete(self, prompt: Prompt, signal: AbortSignal) -> ModelResponse:
        req = ModelRequest(self._ref, prompt.system, prompt.messages, prompt.tools, self.params)
        start = time.monotonic()
        res = await self.scheduler.run(self.endpoint.id, lambda: self.endpoint.complete(req, self.caps, signal), signal)
        return self._account(res, start)

    async def stream(self, prompt: Prompt, signal: AbortSignal) -> AsyncIterator[ModelEvent]:
        req = ModelRequest(self._ref, prompt.system, prompt.messages, prompt.tools, self.params)
        start = time.monotonic()
        events: asyncio.Queue = asyncio.Queue()

        async def pump():  # runs inside the scheduler, so the stream holds an endpoint slot
            async for e in self.endpoint.stream(req, self.caps, signal):
                await events.put(e)

        task = asyncio.create_task(self.scheduler.run(self.endpoint.id, pump, signal))
        task.add_done_callback(lambda _: events.put_nowait(None))
        while (e := await events.get()) is not None:
            if e["type"] == "response_complete":
                self._account(e["response"], start)
            yield e
        await task  # re-raises a failure

    async def start(self) -> None:
        await self.endpoint.start()

    async def aclose(self) -> None:
        await self.endpoint.aclose()

    def _account(self, res: ModelResponse, start: float) -> ModelResponse:
        res.usage["elapsed_ms"] = (time.monotonic() - start) * 1000
        res.usage["cost_usd"] = self.endpoint.cost(res.usage)
        return res
