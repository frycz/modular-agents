"""CombinedToolSet: several tool sets and single tools, seen by the model as one."""

from __future__ import annotations

from modular_agents.interfaces.model import ToolDefinition
from modular_agents.interfaces.tools import Tool, ToolSet


class CombinedToolSet(ToolSet):
    def __init__(self, *parts: ToolSet | Tool):
        self.parts = parts

    def definitions(self) -> list[ToolDefinition]:
        definitions = [d for p in self.parts for d in (p.definitions() if isinstance(p, ToolSet) else [p.definition])]
        names = [d["name"] for d in definitions]
        if clashes := {n for n in names if names.count(n) > 1}:  # checked on every call: parts may change their tools
            raise ValueError(f"tool names used more than once: {', '.join(sorted(clashes))}")
        return definitions

    def get(self, name: str) -> Tool | None:
        for p in self.parts:
            tool = p.get(name) if isinstance(p, ToolSet) else (p if p.definition["name"] == name else None)
            if tool:
                return tool
        return None

    async def start(self) -> None:
        for p in self.parts:
            await p.start()

    async def aclose(self) -> None:
        for p in self.parts:
            await p.aclose()
