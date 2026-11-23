# Tools

Tools are what an agent can do beyond producing text: run commands, read files, call services or operate devices. A tool is a definition and a handler. The definition is sent to the model in the prompt, so the model knows the tool exists and how to call it. The handler runs when the model calls the tool.

## The interface

```python
class Tool(ABC):
    readonly: bool = False  # only looks, never changes anything
    concurrent: bool = False  # may run at the same time as other calls of the same turn

    @property
    def definition(self) -> ToolDefinition: ...  # name, description, input_schema

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput: ...


@dataclass
class ToolOutput:
    content: list[ContentBlock]
    is_error: bool = False
```

`definition` holds the tool's name, a description for the model and a JSON Schema of the input. It is a property, so it can depend on the tool's configuration, and a plain class attribute works too.

`execute()` does the work and returns a `ToolOutput`. Problems the model should react to, such as a missing file, are returned with `is_error=True`. An exception raised by a tool is caught by the loop and reported to the model as an error result too, so a failing tool never ends the run.

`readonly` and `concurrent` describe the tool to the rest of the system. A read-only tool can be allowed freely by permission rules. Concurrent tools may run in parallel: when the model asks for several calls in one turn, the [loop](loop.md) runs consecutive concurrent calls together and every other call alone, in the order the model asked.

## Writing tools

Three tools over a small in-memory notebook:

```python
--8<-- "docs/examples/tools.py:tools"
```

`schema()` builds an input schema in which every property is a required string. `text_output()` wraps text in a `ToolOutput`.

## Tool sets

The harness does not hold tools directly but a tool set: what the agent offers to the model.

```python
class ToolSet(ABC):
    def definitions(self) -> list[ToolDefinition]: ...
    def get(self, name: str) -> Tool | None: ...
```

The loop asks for the definitions on every step, so a tool set may change during a run, for example when a connected server adds tools. `StaticToolSet` holds a fixed list of tools and rejects two tools with the same name. `CombinedToolSet` joins several tool sets and single tools into one:

```python
--8<-- "docs/examples/tools.py:sets"
```

Output:

```text
['list_notes', 'read_note']
['list_notes', 'read_note', 'write_note']
```

## Calling a tool directly

A tool does not need a model or a loop. Called on its own, it gets no context:

```python
--8<-- "docs/examples/tools.py:direct"
```

Output:

```text
ToolOutput(content=[{'type': 'text', 'text': 'milk, eggs, coffee'}], is_error=False)
ToolOutput(content=[{'type': 'text', 'text': 'there is no note titled diary'}], is_error=True)
```

This makes tools easy to test in isolation.

## Tool context

Inside a run, the loop passes a `ToolContext` to every call:

```python
@dataclass
class ToolContext:
    signal: AbortSignal  # set when the run is cancelled
    budget: Budget  # the run's budget; sub-agents hang their budgets from it
    run_id: str
    state: RunState | None = None  # the caller's state; tools may keep data in state.data
    events: EventBus | None = None  # to report progress or ask for approval
    inbox: Inbox | None = None  # to deliver results later, e.g. from a background task
```

A long-running tool watches `signal` to stop when the run is cancelled. A tool that runs an agent hangs that agent's budget from `budget`, as described on the [Composition](composition.md) page. A tool that needs to remember something across calls keeps it in `state.data`, which is saved with the run; the [State](state.md) page shows an example.

## Ready blocks

`StaticToolSet` and `CombinedToolSet`: tool sets.

`SpawnAgentTool` and `Blueprint.as_tool()`: agents as tools, described on the [Composition](composition.md) page.

`schema()`, `text_output()` and `signal()`: helpers for writing tools, in `modular_agents.composites.tools.tool_helpers`.
