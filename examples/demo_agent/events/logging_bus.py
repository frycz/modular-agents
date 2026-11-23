"""LoggingEventBus: logs every event to stderr and denies tools by name."""

from __future__ import annotations

import sys

from modular_agents.interfaces.events import Decision, Deny, EventBus, InterceptableEvent, LoopEvent


class LoggingEventBus(EventBus):
    def __init__(self, denied_tools: set[str] = frozenset(), quiet: bool = False):
        self.denied_tools = denied_tools
        self.quiet = quiet
        self.log: list[LoopEvent] = []

    def emit(self, e: LoopEvent) -> None:
        self.log.append(e)
        if not self.quiet and e["type"] != "delta":  # deltas would print one line per chunk
            details = " ".join(f"{k}={str(v)[:80]!r}" for k, v in e.items() if k != "type")
            print(f"[{e['type']}] {details}", file=sys.stderr)

    async def intercept(self, e: InterceptableEvent) -> Decision:
        return Deny() if e["type"] == "tool_call" and e["name"] in self.denied_tools else "allow"
