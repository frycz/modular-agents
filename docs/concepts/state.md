# State and run store

The state is the complete record of a run: the system prompt, the conversation, what is left of the budget, and metadata. It is plain data, so a run can be saved and resumed later, inspected after it ends or moved to another machine, with no change to the loop.

## Run state

```python
@dataclass
class RunState:
    system: str | list[TextBlock]
    messages: list[Message]
    budget: BudgetState  # what is left of the budget, as of the last step
    meta: RunMeta  # e.g. {"model": "claude-haiku-5-5"}
    id: str  # generated
    parent_id: str | None = None  # the run that started this one, for sub-agents
    context_tokens: int = 0  # size of the conversation as of the last response
    data: dict[str, Any] = {}  # owned by tools and policies, saved with the run
```

`data` belongs to tools and policies: a to-do list, a permission mode or facts collected during the run. Because it is part of the state, it is saved and resumed with the conversation.

## Initial state

An agent does not start from a `RunState` but from an `InitialState`: the system prompt and, optionally, messages to start with, such as examples of the expected answers. The agent turns it into a fresh `RunState` when it is created, and copies the messages, so one initial state can serve many agents.

```python
@dataclass
class InitialState:
    system: str | list[TextBlock] = ""
    messages: list[Message] = []
```

## Keeping data in the state

A tool that remembers facts in `state.data`:

```python
--8<-- "docs/examples/state.py:remember"
```

After one run, the state holds the conversation, the facts and what is left of the budget:

```python
--8<-- "docs/examples/state.py:run"
```

Output:

```text
id: a291d349
messages: 4
data: {'facts': ['the meeting is on Friday']}
budget left: 3 steps
```

## Run store

A run store saves the state after every step of the loop, so a run can be inspected while it is going, examined after it ends, and resumed.

```python
class RunStore(ABC):
    async def save(self, state: RunState) -> None: ...
    async def load(self, id: str) -> RunState | None: ...
```

A store that keeps every run as JSON in memory. A store backed by files or a database follows the same pattern:

```python
--8<-- "docs/examples/state.py:store"
```

## Resuming a run

An agent created with a saved state continues that conversation instead of starting a new one. Its initial state is then ignored:

```python
--8<-- "docs/examples/state.py:resume"
```

Output:

```text
The meeting is on Friday.
messages: 6 facts: ['the meeting is on Friday']
```

The resumed agent sees the whole earlier conversation and the facts kept by the tool.

## Ready blocks

The library defines the `RunStore` interface and leaves storage to the application. The demo agent in the repository's `examples/` directory has `JsonRunStore`, which writes one JSON file per run.
