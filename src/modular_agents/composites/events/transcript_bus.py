"""TranscriptBus: prints tool calls and results as a tree, one line per event."""

from __future__ import annotations

from contextvars import ContextVar

from modular_agents.interfaces.events import Decision, EventBus, InterceptableEvent, LoopEvent

path: ContextVar[tuple[str, ...]] = ContextVar("path", default=())  # where in the agent tree the current run is, set by AgentTool


class TranscriptBus(EventBus):
    """Prints tool calls and results, indented by how deep the agent is nested and labelled with its path in the tree."""

    def __init__(self, label: str, width: int = 110):
        self.label = label
        self.width = width

    def say(self, text: str) -> None:
        where = path.get()
        line = f"{'    ' * len(where)}[{'/'.join(where) or self.label}] {' '.join(text.split())}"
        print(line if len(line) <= self.width else line[: self.width - 1] + "…")

    def emit(self, e: LoopEvent) -> None:
        match e["type"]:
            case "tool_call":
                self.say(f"→ {e['name']}({', '.join(f'{k}={v!r}' for k, v in e['input'].items())})")
            case "tool_result":
                text = " ".join(b["text"] for b in e["content"] if b["type"] == "text")
                self.say(f"{'✗' if e['is_error'] else '←'} {e['name']}: {text}")
            case "done":
                self.say(f"■ done ({e['reason']})")

    async def intercept(self, e: InterceptableEvent) -> Decision:
        return "allow"
