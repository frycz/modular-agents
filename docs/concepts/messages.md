# Messages

The blocks of an agent exchange data only: values that carry no behaviour and can be serialized to JSON. No block passes an object with methods, or a reference to its internals, to another block. This keeps the blocks independent and makes every exchange possible to log, store and replay.

This page describes the three kinds of data that flow through a run: the conversation, the prompt and the response.

## Conversation

A conversation is a list of messages. Each message has a role and a list of content blocks. The role is `user` for what comes into the agent and `assistant` for what the model produced.

```python
class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: list[ContentBlock]
```

A content block is one piece of content, identified by its `type`:

- `text`: plain text.
- `tool_call`: a call the model asks for, with an `id`, the tool `name` and its `input`.
- `tool_result`: the answer to a tool call, with the `call_id` it answers, its `content` and an `is_error` flag.
- `thinking`: the model's reasoning, when the model produces it.
- `image` and `document`: base64 data with a media type, for models that accept them.
- `opaque`: provider-only content with no common form, such as the results of a search run on the provider's side. It is kept for the provider that produced it and dropped by others.

A run with one tool call, as a conversation:

```python
--8<-- "docs/examples/messages.py:conversation"
```

Tool results travel in `user` messages, because they come into the agent from outside the model. All results of one turn go back in a single message, and the ids pair every result with its call.

### Provider data

Any content block may carry `ext`: provider-specific data keyed by protocol name, such as `{"anthropic": {"cache_control": {"type": "ephemeral"}}}`. A protocol adapter sends its own key's data and ignores the others, so a conversation can move to another provider without carrying wire formats along.

## Prompt

A prompt is what the model receives on one call: the system prompt (the standing instructions that define the agent), the conversation and the definitions of the tools the model may call.

```python
@dataclass
class Prompt:
    system: str | list[TextBlock]
    messages: list[Message]
    tools: list[ToolDefinition] = []


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict  # JSON Schema of the input
```

A tool definition tells the model what a tool does and what input it takes. The first prompt of the run above, with one tool:

```python
--8<-- "docs/examples/messages.py:prompt"
```

The loop builds a new prompt from the state before every model call, and the [context policy](context-policy.md) may adjust it.

## Response

A response is what the model returns: new content blocks, the reason it stopped and what the call used.

```python
@dataclass
class ModelResponse:
    content: list[ContentBlock]
    stop_reason: StopReason
    usage: Usage


class Usage(TypedDict):
    input_tokens: int
    output_tokens: int
    cost_usd: float
    elapsed_ms: float
    cache_read_tokens: NotRequired[int]
    cache_write_tokens: NotRequired[int]
```

The stop reason tells the loop what to do next:

- `end_turn`: the model has finished.
- `tool_use`: the model asks for tool calls.
- `max_tokens`: the model was cut off at the output limit.
- `pause_turn`: the provider paused a long turn; the loop calls the model again.
- `refusal`: the model declined to continue.

A response in which the model asks for a tool call:

```python
--8<-- "docs/examples/messages.py:response"
```

## Everything is data

Prompts, responses and whole conversations survive a round trip through JSON unchanged:

```python
--8<-- "docs/examples/messages.py:json"
```

Output:

```text
{
  "content": [
    {
      "type": "tool_call",
      "id": "c1",
      "name": "read_file",
      "input": {
        "path": "notes.txt"
      }
    }
  ],
  "stop_reason": "tool_use",
  "usage": {
    "input_tokens": 120,
    "output_tokens": 25,
    "cost_usd": 0.0004,
    "elapsed_ms": 800
  }
}
```

The same holds for the [state of a run](state.md), which is why runs can be saved, inspected and resumed.

The full definitions are in [`interfaces/messages.py`](../reference/interfaces.md#messages) and [`interfaces/model.py`](../reference/interfaces.md#model).
