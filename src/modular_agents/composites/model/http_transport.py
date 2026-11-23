"""HttpTransport: POSTs JSON to one URL. Streams are read as server-sent events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from modular_agents.composites.helpers import abortable
from modular_agents.interfaces.cancellation import AbortSignal, Cancelled
from modular_agents.interfaces.endpoint import RetryableError, Transport, WireChunk, WireRequest, WireResponse

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


class HttpTransport(Transport):
    def __init__(self, url: str, headers: dict[str, str], timeout_s: float = 600):
        self.url = url
        self.headers = headers
        self.client = httpx.AsyncClient(timeout=timeout_s)

    async def send(self, req: WireRequest, signal: AbortSignal) -> WireResponse:
        try:
            res = await abortable(self.client.post(self.url, json=req, headers=self.headers), signal)
        except httpx.TransportError as e:
            raise RetryableError(str(e)) from e
        self._check(res.status_code, res.text)
        return res.json()

    async def stream(self, req: WireRequest, signal: AbortSignal) -> AsyncIterator[WireChunk]:
        try:
            async with self.client.stream("POST", self.url, json={**req, "stream": True}, headers=self.headers) as res:
                if res.status_code >= 400:
                    self._check(res.status_code, (await res.aread()).decode())
                async for line in res.aiter_lines():
                    if signal.is_set():
                        raise Cancelled()
                    if line.startswith("data:"):
                        yield json.loads(line[5:])
        except httpx.TransportError as e:
            raise RetryableError(str(e)) from e

    async def aclose(self) -> None:
        await self.client.aclose()

    def _check(self, status: int, body: str):
        if status >= 400:
            error = RetryableError if status in RETRYABLE_STATUS else RuntimeError
            raise error(f"HTTP {status}: {body[:500]}")
