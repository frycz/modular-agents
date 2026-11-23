"""Lifecycle: parts that hold connections or processes (an MCP server, an HTTP client, a container) start and close."""

from __future__ import annotations


class Resource:
    """start() before the first run, aclose() after the last. Parts are shared between agents, so both may be called
    more than once and must be idempotent. The defaults do nothing, so stateless parts need not care."""

    async def start(self) -> None:
        pass

    async def aclose(self) -> None:
        pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()
