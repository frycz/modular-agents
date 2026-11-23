"""TruncatingContextPolicy: cuts long tool outputs in what the model sees."""

from __future__ import annotations

from dataclasses import replace

from modular_agents.interfaces.messages import Message
from modular_agents.interfaces.model import Model, Prompt
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.state import RunState


class TruncatingContextPolicy(ContextPolicy):
    """Cuts long tool outputs. Compaction or caching would go in another policy."""

    def __init__(self, max_result_chars: int = 10_000):
        self.max_result_chars = max_result_chars

    async def prepare(self, state: RunState, prompt: Prompt, model: Model) -> Prompt:
        return replace(prompt, messages=[self._trim(m) for m in prompt.messages])

    def _trim(self, message: Message) -> Message:
        # Long tool outputs are cut in what is sent, the stored state keeps them whole.
        content = []
        for block in message["content"]:
            if block["type"] == "tool_result":
                block = {**block, "content": [self._trim_text(b) for b in block["content"]]}
            content.append(block)
        return {**message, "content": content}

    def _trim_text(self, block):
        if block["type"] == "text" and len(block["text"]) > self.max_result_chars:
            return {**block, "text": block["text"][: self.max_result_chars] + "\n[truncated]"}
        return block
