"""Messages, prompts and responses are plain data."""

import json
from dataclasses import asdict

from modular_agents.interfaces.model import ModelResponse, Prompt

# --8<-- [start:conversation]
conversation = [
    {"role": "user", "content": [{"type": "text", "text": "How many lines does notes.txt have?"}]},
    {"role": "assistant", "content": [
        {"type": "tool_call", "id": "c1", "name": "read_file", "input": {"path": "notes.txt"}},
    ]},
    {"role": "user", "content": [
        {"type": "tool_result", "call_id": "c1", "is_error": False,
         "content": [{"type": "text", "text": "first\nsecond\nthird"}]},
    ]},
    {"role": "assistant", "content": [{"type": "text", "text": "notes.txt has 3 lines."}]},
]
# --8<-- [end:conversation]

# --8<-- [start:prompt]
read_file = {
    "name": "read_file",
    "description": "Read a text file and return its content.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}
prompt = Prompt(
    system="You are a helpful assistant.",
    messages=conversation[:1],  # the first call sees only the task
    tools=[read_file],
)
# --8<-- [end:prompt]

# --8<-- [start:response]
response = ModelResponse(
    content=[{"type": "tool_call", "id": "c1", "name": "read_file", "input": {"path": "notes.txt"}}],
    stop_reason="tool_use",
    usage={"input_tokens": 120, "output_tokens": 25, "cost_usd": 0.0004, "elapsed_ms": 800},
)
# --8<-- [end:response]

# --8<-- [start:json]
data = {"prompt": asdict(prompt), "response": asdict(response)}
assert json.loads(json.dumps(data)) == data  # a round trip through JSON loses nothing
print(json.dumps(data["response"], indent=2))
# --8<-- [end:json]
