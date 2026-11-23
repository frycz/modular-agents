"""A model written from scratch: answers with the task in capitals. No network, no API key."""

import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.helpers import message_text
from modular_agents.interfaces.model import Capabilities, Model, ModelResponse, Prompt


# --8<-- [start:model]
class ShoutingModel(Model):
    @property
    def ref(self):
        return "shouting-1"

    async def complete(self, prompt, signal):
        last = prompt.messages[-1]
        text = " ".join(b["text"] for b in last["content"] if b["type"] == "text")
        return ModelResponse(
            content=[{"type": "text", "text": text.upper()}],
            stop_reason="end_turn",
            usage={"input_tokens": len(text) // 4, "output_tokens": len(text) // 4, "cost_usd": 0.0, "elapsed_ms": 0.0},
        )

    async def stream(self, prompt, signal):
        # A model without real streaming yields only the final event.
        yield {"type": "response_complete", "response": await self.complete(prompt, signal)}

    def capabilities(self):
        return Capabilities(tool_calling=False)
# --8<-- [end:model]


# --8<-- [start:use]
async def main():
    model = ShoutingModel()

    # Called directly, with a prompt and a cancellation signal.
    prompt = Prompt(system="", messages=[{"role": "user", "content": [{"type": "text", "text": "hello"}]}])
    response = await model.complete(prompt, asyncio.Event())
    print(response.content, response.stop_reason)

    # Or as the model of an agent.
    agent = ComposedAgent(model=model)
    outcome = await agent.run("a model is just an interface")
    print(message_text(outcome.final))


asyncio.run(main())
# --8<-- [end:use]
