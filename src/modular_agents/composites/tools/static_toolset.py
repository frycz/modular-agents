"""StaticToolSet: a fixed list of tools."""

from __future__ import annotations

from modular_agents.interfaces.model import ToolDefinition
from modular_agents.interfaces.tools import Tool, ToolSet


class StaticToolSet(ToolSet):
    def __init__(self, tools: list[Tool]):
        self.tools: dict[str, Tool] = {}
        for t in tools:
            name = t.definition["name"]
            if name in self.tools:
                raise ValueError(f"two tools are named {name}")
            self.tools[name] = t

    def definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self.tools.values()]

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    async def start(self) -> None:
        for t in self.tools.values():
            await t.start()

    async def aclose(self) -> None:
        for t in self.tools.values():
            await t.aclose()
