"""LiveStatusPolicy: shows the model the devices' current state on every call, without storing it in the context."""

from __future__ import annotations

from dataclasses import replace

from modular_agents.composites.devices.device import Device
from modular_agents.interfaces.budget import Budget
from modular_agents.interfaces.cancellation import AbortSignal
from modular_agents.interfaces.model import Model, Prompt
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.state import RunState


class LiveStatusPolicy(ContextPolicy):
    def __init__(self, devices: list[Device], inner: ContextPolicy | None = None):
        self.devices = devices
        self.inner = inner  # policies stack: the inner one prepares first

    async def prepare(self, state: RunState, prompt: Prompt, model: Model) -> Prompt:
        prompt = await self.inner.prepare(state, prompt, model) if self.inner else prompt
        status = "; ".join(f"{d.name}: {d.status()}" for d in self.devices)
        *rest, last = prompt.messages
        return replace(prompt, messages=rest + [{**last, "content": last["content"] + [{"type": "text", "text": f"[live status] {status}"}]}])

    def needs_compaction(self, state: RunState, model: Model) -> bool:
        return bool(self.inner) and self.inner.needs_compaction(state, model)

    async def compact(self, state: RunState, model: Model, budget: Budget, signal: AbortSignal) -> None:
        if self.inner:
            await self.inner.compact(state, model, budget, signal)
