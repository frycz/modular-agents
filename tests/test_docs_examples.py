"""Every code example of the documentation is a file in docs/examples/ and must run.

Examples that call Claude run against a fake HTTP transport unless ANTHROPIC_API_KEY is set, so they are checked
offline too: everything up to the HTTP request is real.
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path

import pytest

from modular_agents.composites.model import anthropic_model, http_transport

EXAMPLES = sorted((Path(__file__).parent.parent / "docs" / "examples").glob("*.py"))


class FakeTransport(http_transport.HttpTransport):
    """Answers every request with the same short text, in the Anthropic wire format."""

    ANSWER = "(an answer from the fake transport)"

    async def send(self, req, signal):
        return {
            "content": [{"type": "text", "text": self.ANSWER}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    async def stream(self, req, signal):
        yield {"type": "message_start", "message": {"usage": {"input_tokens": 10, "output_tokens": 0}}}
        yield {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": self.ANSWER}}
        yield {"type": "content_block_stop", "index": 0}
        yield {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 5}}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_runs(path, monkeypatch, tmp_path):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
        monkeypatch.setattr(http_transport, "HttpTransport", FakeTransport)
        monkeypatch.setattr(anthropic_model, "HttpTransport", FakeTransport)
    monkeypatch.chdir(tmp_path)  # examples that write files write them here
    monkeypatch.syspath_prepend(str(path.parent))  # as when run as a script: examples may import each other
    runpy.run_path(str(path), run_name="__main__")
