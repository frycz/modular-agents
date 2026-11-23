"""GuardBus: wraps any bus and adds safety rules on tool calls."""

from __future__ import annotations

import math
from collections.abc import Callable

from modular_agents.interfaces.events import Decision, Deny, EventBus, InterceptableEvent, LoopEvent, Modify, ToolCallEvent

type Rule = Callable[[ToolCallEvent], tuple[Decision, str] | None]  # None: no objection


class GuardBus(EventBus):
    """Wraps another bus: events pass through unchanged, tool calls must get past every rule first."""

    def __init__(self, inner: EventBus, *rules: Rule):
        self.inner = inner
        self.rules = rules
        self.report = getattr(inner, "say", lambda text: None)

    def emit(self, e: LoopEvent) -> None:
        self.inner.emit(e)

    async def intercept(self, e: InterceptableEvent) -> Decision:
        decision = await self.inner.intercept(e)
        if e["type"] != "tool_call":  # the rules are about tool calls only
            return decision
        for rule in self.rules:
            if isinstance(decision, Deny):
                break
            current = {**e, "input": decision.value} if isinstance(decision, Modify) else e  # rules see earlier changes
            verdict = rule(current)
            if verdict:
                decision, why = verdict
                self.report(f"⚑ guard: {why}")
        return decision


def forbid(tool: str, reason: str) -> Rule:
    return lambda e: (Deny(reason), f"{tool} denied, {reason}") if e["name"] == tool else None


def clamp(tool: str, field: str, lo: float = -math.inf, hi: float = math.inf) -> Rule:
    """Keeps one numeric input of a tool within bounds, by changing the call instead of denying it."""
    def rule(e: ToolCallEvent):
        if e["name"] != tool or field not in e["input"]:
            return None
        value = e["input"][field]
        bounded = type(value)(min(max(value, lo), hi))
        if bounded == value:
            return None
        return Modify({**e["input"], field: bounded}), f"{tool} {field}={value} is out of range, changed to {bounded}"
    return rule
