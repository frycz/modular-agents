"""The parts behind AnthropicModel: a protocol adapter, a transport, an endpoint and a scheduler."""

import asyncio
import json
import os

from modular_agents.composites.helpers import message_text
from modular_agents.composites.model.adapter_endpoint import AdapterEndpoint
from modular_agents.composites.model.anthropic_adapter import AnthropicAdapter
from modular_agents.composites.model.anthropic_model import AnthropicModel
from modular_agents.composites.model.endpoint_model import EndpointModel
from modular_agents.composites.model.http_transport import HttpTransport
from modular_agents.composites.model.scheduler import SemaphoreScheduler
from modular_agents.interfaces.model import Capabilities, ModelRequest, Prompt

# --8<-- [start:adapter]
adapter = AnthropicAdapter()

request = ModelRequest(
    model="claude-haiku-5-5",
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": [{"type": "text", "text": "Say hello."}]}],
    tools=[],
    params={"max_tokens": 1000},
)
print(json.dumps(adapter.encode(request, Capabilities()), indent=2))

body = {
    "content": [{"type": "tool_use", "id": "toolu_01", "name": "read_file", "input": {"path": "notes.txt"}}],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 410, "output_tokens": 52},
}
print(adapter.decode(body))
# --8<-- [end:adapter]

# --8<-- [start:shortcut]
model = AnthropicModel(ref="claude-haiku-5-5", params={"max_tokens": 2000})
# --8<-- [end:shortcut]


# --8<-- [start:endpoint]
endpoint = AdapterEndpoint(
    id="anthropic",
    adapter=AnthropicAdapter(),
    transport=HttpTransport(
        url="https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
    ),
    input_usd_per_mtok=1.0,  # example prices, in USD per million tokens
    output_usd_per_mtok=5.0,
)
model = EndpointModel(
    endpoint=endpoint,
    ref="claude-haiku-5-5",
    params={"max_tokens": 2000},
    scheduler=SemaphoreScheduler(default_limit=2),  # at most 2 requests to this endpoint at a time
)
# --8<-- [end:endpoint]

# --8<-- [start:call]
async def main():
    async with model:  # opens and closes the HTTP client
        prompt = Prompt(system="", messages=[{"role": "user", "content": [{"type": "text", "text": "Say hello."}]}])
        response = await model.complete(prompt, asyncio.Event())
    print(message_text({"role": "assistant", "content": response.content}))
    print(response.usage)


asyncio.run(main())
# --8<-- [end:call]
