"""Small helpers shared by implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from modular_agents.interfaces.cancellation import AbortSignal, Cancelled
from modular_agents.interfaces.messages import ContentBlock, Message


async def abortable[T](aw: Awaitable[T], signal: AbortSignal) -> T:
    """Await something, but give up as soon as the signal is set."""
    task = asyncio.ensure_future(aw)
    waiter = asyncio.ensure_future(signal.wait())
    try:
        await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if not task.done():
            raise Cancelled()
        return task.result()
    finally:
        waiter.cancel()
        task.cancel()


def message_text(message: Message) -> str:
    return "\n".join(b["text"] for b in message["content"] if b["type"] == "text")


def append_user(messages: list[Message], content: list[ContentBlock]) -> None:
    """Add user content, joining the last message if it is a user one, since roles must alternate."""
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"].extend(content)
    else:
        messages.append({"role": "user", "content": list(content)})
