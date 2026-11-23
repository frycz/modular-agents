"""Small helpers shared by tools."""

from __future__ import annotations

import asyncio

from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.tools import ToolContext, ToolOutput


def schema(**props: str) -> dict:
    """Object schema where every property is a required string."""
    return {
        "type": "object",
        "properties": {name: {"type": "string", "description": desc} for name, desc in props.items()},
        "required": list(props),
    }


def text_output(text: str, is_error: bool = False) -> ToolOutput:
    return ToolOutput([{"type": "text", "text": text}], is_error)


def signal(ctx: ToolContext | None) -> AbortSignal:
    """The run's signal, or one that is never set when the tool is called on its own."""
    return ctx.signal if ctx else asyncio.Event()
