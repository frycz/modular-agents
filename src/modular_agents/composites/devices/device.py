"""Simulated devices: plain Python objects whose @action methods become tools."""

from __future__ import annotations

import inspect

from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.model import ToolDefinition
from modular_agents.interfaces.tools import Tool, ToolContext, ToolOutput

JSON_TYPES = {int: "integer", float: "number", str: "string", bool: "boolean"}


def action(fn=None, *, readonly: bool = False):
    """Marks a device method as a tool. Its docstring is the description, its parameters the input schema."""
    def mark(f):
        f.action = {"readonly": readonly}
        return f
    return mark(fn) if fn else mark


class Device:
    """A toy piece of hardware. Its state lives here, outside any agent's context, so every agent sees the same world."""

    name = "device"
    description = ""

    @action(readonly=True)
    def status(self) -> str:
        """Report the current state."""
        return ", ".join(f"{k}={v}" for k, v in vars(self).items() if not k.startswith("_") and k not in ("name", "description"))

    def actions(self, readonly: bool = False) -> list[ActionTool]:
        fns = [getattr(type(self), n) for n in dir(type(self))]
        return [ActionTool(self, f) for f in fns if hasattr(f, "action") and (f.action["readonly"] or not readonly)]


class ActionTool(Tool):
    """One device method as a tool, named <device>_<method>."""

    def __init__(self, device: Device, fn):
        self.device, self.fn = device, fn
        self.readonly = self.concurrent = fn.action["readonly"]  # looking can happen in parallel, changing cannot

    @property
    def definition(self) -> ToolDefinition:
        params = list(inspect.signature(self.fn, eval_str=True).parameters.values())[1:]  # without self
        return {
            "name": f"{self.device.name}_{self.fn.__name__}",
            "description": f"{inspect.getdoc(self.fn)} Device: {self.device.description or self.device.name}.",
            "input_schema": {
                "type": "object",
                "properties": {p.name: {"type": JSON_TYPES[p.annotation]} for p in params},
                "required": [p.name for p in params if p.default is p.empty],
            },
        }

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        # a device raising ValueError is reported to the model as a tool error by the loop
        return text_output(str(self.fn(self.device, **input)))


class DeviceToolSet(StaticToolSet):
    """The actions of some devices. readonly=True gives a look-but-don't-touch view of the same devices."""

    def __init__(self, *devices: Device, readonly: bool = False):
        super().__init__([t for d in devices for t in d.actions(readonly)])
