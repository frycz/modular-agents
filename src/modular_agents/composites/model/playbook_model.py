"""PlaybookModel: a fake model that follows a written playbook instead of thinking. No API, fully deterministic."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from modular_agents.composites.helpers import abortable
from modular_agents.interfaces.messages import ContentBlock, Message
from modular_agents.interfaces.model import Capabilities, Model, ModelResponse, Prompt


@dataclass
class Call:
    name: str
    input: dict


@dataclass
class Say:
    text: str | Callable[[list[str]], str]  # a callable gets the texts of all tool results of the current task


type Turn = Call | list[Call] | Say  # a list is several tool calls in one turn, run in parallel by the loop


def call(name: str, **input) -> Call:
    return Call(name, input)


def say(text: str | Callable[[list[str]], str]) -> Say:
    return Say(text)


class PlaybookModel(Model):
    """Picks the playbook whose keyword is in the task, then plays one turn per model call.

    Stateless: the position in the playbook is read from the messages, so one instance serves any number of contexts.
    """

    def __init__(self, ref: str, playbooks: dict[str, list[Turn]], delay_s: float = 0.05):
        self._ref = ref
        self.playbooks = playbooks
        self.delay_s = delay_s  # pretend to think, so parallel calls are visible

    @property
    def ref(self) -> str:
        return self._ref

    async def complete(self, prompt: Prompt, signal) -> ModelResponse:
        await abortable(asyncio.sleep(self.delay_s), signal)
        messages = prompt.messages
        task, turns_done, results = self._progress(messages)
        playbook = next((p for keyword, p in self.playbooks.items() if keyword in task.lower()), None)
        if playbook is None:
            turn = Say(f"I only know playbooks for: {', '.join(self.playbooks)}.")
        else:
            turn = playbook[turns_done] if turns_done < len(playbook) else Say("(end of playbook)")

        if isinstance(turn, Say):
            text = turn.text(results) if callable(turn.text) else turn.text
            content: list[ContentBlock] = [{"type": "text", "text": text}]
            stop = "end_turn"
        else:
            calls = turn if isinstance(turn, list) else [turn]
            content = [{"type": "tool_call", "id": uuid.uuid4().hex[:8], "name": c.name, "input": c.input} for c in calls]
            stop = "tool_use"
        input_tokens, output_tokens = len(str(messages)) // 4, len(str(content)) // 4
        usage = {
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": (input_tokens * 3 + output_tokens * 15) / 1e6, "elapsed_ms": self.delay_s * 1000,
        }
        return ModelResponse(content, stop, usage)

    async def stream(self, prompt: Prompt, signal):
        yield {"type": "response_complete", "response": await self.complete(prompt, signal)}

    def capabilities(self) -> Capabilities:
        return Capabilities()

    @staticmethod
    def _progress(messages: list[Message]) -> tuple[str, int, list[str]]:
        """The current task, how many turns were played for it, and the tool results so far."""
        start = next((i for i in range(len(messages) - 1, -1, -1) if PlaybookModel._is_task(messages[i])), None)
        if start is None:
            return "", 0, []
        after = messages[start + 1:]
        results = [
            "\n".join(c["text"] for c in b["content"] if c["type"] == "text")
            for m in after for b in m["content"] if b["type"] == "tool_result"
        ]
        return messages[start]["content"][0]["text"], sum(m["role"] == "assistant" for m in after), results

    @staticmethod
    def _is_task(m: Message) -> bool:
        # a task message starts with text; tool result messages start with a tool_result
        return m["role"] == "user" and bool(m["content"]) and m["content"][0]["type"] == "text"
