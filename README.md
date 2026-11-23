# modular-agents

A modular architecture for LLM agents: technology-agnostic building blocks with defined interfaces, and a reference implementation in Python.

An agent is a model run in a loop. The model reads the conversation so far and decides the next step: answer, or ask for a tool to be used. The harness runs the loop: it sends the conversation to the model, executes the requested tools, adds the results to the conversation and asks the model again. Everything around this loop, such as how much an agent may spend, what it is allowed to do, what the model sees and what gets saved, is a separate building block behind its own interface.

A new agent is made by replacing, adding or removing building blocks. Swapping a hosted model for a local one, giving an agent a new tool or putting a permission check in front of its tools is each a change to one block, with the rest of the agent untouched.

Because an agent is only a composition of blocks, one agent can be a tool of another. The parent sees an ordinary tool, the child runs in its own fresh context, and its spending is charged to the parent's budget. Agents nested this way form a tree, which can be printed, limited and observed as a whole.

The interfaces are not tied to a language, a model provider or a runtime. This repository expresses them in Python and implements them as a Python package, which also serves as a working example of the architecture.

Status: alpha. The interfaces may still change.

Documentation: https://frycz.github.io/modular-agents/

## The building blocks

Each building block is a small interface, most of them with one to three methods. The interfaces below are abridged: lifecycle methods (`start()` and `aclose()`) and some optional parts are left out. The full definitions are in [`src/modular_agents/interfaces/`](src/modular_agents/interfaces).

### Messages

The data that flows between the blocks. A conversation is a list of messages, and each message is a list of content blocks: text, a tool call requested by the model, or the result of a tool call.

```python
class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: list[ContentBlock]  # text, tool_call, tool_result, image, thinking, ...
```

### Model

Takes a prompt and returns a response with text, tool calls or both.

```python
class Model(ABC):
    async def complete(self, prompt: Prompt, signal: AbortSignal) -> ModelResponse: ...
    def stream(self, prompt: Prompt, signal: AbortSignal) -> AsyncIterator[ModelEvent]: ...


@dataclass
class Prompt:
    system: str
    messages: list[Message]
    tools: list[ToolDefinition]


@dataclass
class ModelResponse:
    content: list[ContentBlock]
    stop_reason: StopReason  # "end_turn", "tool_use", "max_tokens", ...
    usage: Usage  # tokens, cost and time of this call
```

Ready blocks: `AnthropicModel` talks to Claude. `PlaybookModel` is a fake model that follows a written script, for tests and offline runs.

### Tools

What an agent can do beyond producing text. A tool has a definition, which the model sees, and an `execute()` method, which runs the call. A tool set is what the agent offers to the model.

```python
class Tool(ABC):
    readonly: bool = False  # only looks, never changes anything
    concurrent: bool = False  # may run at the same time as other calls of the same turn

    @property
    def definition(self) -> ToolDefinition: ...  # name, description, input_schema
    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput: ...


class ToolSet(ABC):
    def definitions(self) -> list[ToolDefinition]: ...
    def get(self, name: str) -> Tool | None: ...
```

Ready blocks: `StaticToolSet` holds a fixed list of tools. `CombinedToolSet` joins several tool sets and single tools into one.

### Loop

Calls the model, runs the tool calls it asks for, adds the results to the conversation and repeats until the model answers or something stops it.

```python
class Loop(ABC):
    async def run(self, state: RunState, ctx: RunContext) -> RunOutcome: ...
```

`RunState` is the conversation of one run as plain, serializable data. `RunContext` carries the other blocks the loop works with: the model, the budget, the tools, the context policy, the event bus and the run store.

Ready block: `StandardLoop` streams every model call and runs concurrent tools in parallel.

### Budget

The stop condition: how many steps, tokens, dollars and milliseconds a run may use.

```python
class Budget(ABC):
    def remaining(self) -> BudgetState: ...
    def charge(self, usage: Usage) -> None: ...  # also charged to all ancestors
    def child(self, limit: BudgetLimit) -> Budget: ...  # capped by what the parent has left
```

Ready block: `TreeBudget`. A sub-agent gets a child of its parent's budget, so a limit on the top agent covers the whole tree.

### Events

Every step of the loop is reported as an event. Some events, such as a tool call, can also be intercepted: allowed, denied or changed before they take effect.

```python
class EventBus(ABC):
    def emit(self, e: LoopEvent) -> None: ...  # observation: logging, tracing, UI
    async def intercept(self, e: InterceptableEvent) -> Decision: ...  # "allow", Deny(reason) or Modify(value)
```

Ready blocks: `TranscriptBus` prints the run as a tree. `GuardBus` wraps another bus and adds rules such as `forbid()` and `clamp()`.

### Context policy

Decides what the model sees on each call, for example by truncating old tool results or adding live status, without changing the conversation itself.

```python
class ContextPolicy(ABC):
    async def prepare(self, state: RunState, prompt: Prompt, model: Model) -> Prompt: ...
```

### Run store

Saves the conversation after each step, so a run can be inspected or resumed.

```python
class RunStore(ABC):
    async def save(self, state: RunState) -> None: ...
    async def load(self, id: str) -> RunState | None: ...
```

### Harness

Everything around the model in one object. Only the loop and the budget are required, so an agent always has a stop condition.

```python
@dataclass
class Harness:
    loop: Loop
    budget: Budget
    tools: ToolSet | None = None  # none: the model can only answer in text
    policy: ContextPolicy | None = None  # none: the model sees the conversation as it is
    events: EventBus | None = None  # none: nothing observed, every tool call allowed
    store: RunStore | None = None  # none: nothing saved
```

### Agent

A model plus a harness, owning one conversation. Each `run(task)` adds the task to the conversation and runs the loop until it stops.

```python
class Agent(ABC):
    async def run(self, task: str, signal: AbortSignal) -> RunOutcome: ...  # reason, final message, state
```

Ready blocks: `ComposedAgent` is built from a model and a harness. `Blueprint` describes an agent once, so it can run on its own or serve as another agent's tool.

## Install

The Python implementation requires Python 3.12 or newer.

```sh
pip install modular-agents
```

Until the first release, the package is installed from GitHub:

```sh
pip install git+https://github.com/frycz/modular-agents
```

The package depends only on `httpx`.

## Composing an agent

The steps below compose a research agent that searches notes. Then they add a writer agent that uses the research agent as a tool.

### 1. A tool

The tool is the only block written by hand. It implements the `Tool` interface:

```python
from modular_agents.composites.tools.tool_helpers import text_output
from modular_agents.interfaces.tools import Tool


class SearchNotes(Tool):
    readonly = concurrent = True  # only reads, so it may run in parallel with other tool calls

    def __init__(self, notes: list[str]):
        self.notes = notes

    @property
    def definition(self):
        return {
            "name": "search_notes",
            "description": "Find notes that mention a word.",
            "input_schema": {
                "type": "object",
                "properties": {"word": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["word"],
            },
        }

    async def execute(self, input, ctx=None):
        found = [n for n in self.notes if input["word"].lower() in n.lower()][: input.get("limit", 3)]
        return text_output(text=" ".join(found) or "no notes found")


NOTES = [
    "The budget limits steps, tokens, cost and time.",
    "A run stops when the model answers or the budget runs out.",
    "A sub-agent's spending is charged to its parent's budget.",
    "Tool calls can be denied or changed by the event bus.",
]
```

### 2. A harness

The harness puts the ready blocks around the tool. Here the agent may take at most 5 steps, its tool calls are printed, and a guard keeps the `limit` of every search at 2 or less by changing any call that asks for more:

```python
from modular_agents.composites.budget.tree_budget import TreeBudget
from modular_agents.composites.events.guard_bus import GuardBus, clamp
from modular_agents.composites.events.transcript_bus import TranscriptBus
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.tools.static_toolset import StaticToolSet
from modular_agents.interfaces.harness import Harness

research_harness = Harness(
    loop=StandardLoop(),
    budget=TreeBudget(limit={"steps": 5}),
    tools=StaticToolSet(tools=[SearchNotes(notes=NOTES)]),
    events=GuardBus(TranscriptBus(label="research_agent"), clamp(tool="search_notes", field="limit", hi=2)),
)
```

The first argument of `GuardBus` is the bus it wraps, the rest are its rules. `forbid(tool=..., reason=...)` denies a tool outright, and any plain function that takes a tool call and returns a decision can serve as a rule.

### 3. An agent

The agent is the model plus the harness, with a system prompt to start its conversation:

```python
import asyncio

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.helpers import message_text
from modular_agents.composites.model.anthropic_model import AnthropicModel
from modular_agents.interfaces.state import InitialState

research_agent = ComposedAgent(
    model=AnthropicModel(ref="claude-haiku-5-5"),  # the API key is read from ANTHROPIC_API_KEY
    harness=research_harness,
    initial_state=InitialState(system="Search the notes and report what they say about the topic."),
)


async def main():
    async with research_agent:  # starts and closes the model's HTTP client and the tools
        outcome = await research_agent.run("What do the notes say about the budget?")
        print(message_text(outcome.final))
        outcome = await research_agent.run("And about sub-agents?")  # the same conversation continues
        print(message_text(outcome.final))


asyncio.run(main())
```

`run()` returns a `RunOutcome` with the reason the run stopped (`end_turn`, `budget_exhausted`, `cancelled` and so on), the final message and the whole conversation.

Replacing a block is a change to one argument. A different model, another tool set, a stricter budget or a context policy each leave the rest of the agent as it is.

### 4. An agent as a tool

A `Blueprint` holds the same parts as the agent above, plus a name and a description. `as_tool()` turns it into a tool for another agent, and every call to that tool runs the agent in a fresh conversation, charged to the caller's budget. The writer agent has one tool, the research agent:

```python
from modular_agents.composites.agent.blueprint import Blueprint

research_agent = Blueprint(
    name="research_agent",
    description="searches the notes and reports what they say.",
    model=AnthropicModel(ref="claude-haiku-5-5"),
    harness=research_harness,
    initial=InitialState(system="Search the notes and report what they say about the topic."),
)
writer_agent = Blueprint(
    name="writer_agent",
    description="writes short summaries.",
    model=AnthropicModel(ref="claude-sonnet-5-5"),
    harness=Harness(
        loop=StandardLoop(),
        budget=TreeBudget(limit={"steps": 10}),
        tools=StaticToolSet(tools=[research_agent.as_tool()]),
        events=TranscriptBus(label="writer_agent"),
    ),
    initial=InitialState(system="Write short summaries. Ask the research agent for the facts."),
)

print(writer_agent.tree())


async def main():
    session = TreeBudget(limit={"tokens": 200_000})  # every model call in the whole tree is charged here
    async with writer_agent.agent(session_budget=session) as agent:
        outcome = await agent.run("Write a one-line summary of how the budget works.")
    print(message_text(outcome.final))
    print(session.spent)


asyncio.run(main())
```

The two agents use different models: a smaller one does the searching, a stronger one writes.

`tree()` prints the composition:

```text
writer_agent [claude-sonnet-5-5]: writes short summaries.
  harness: StandardLoop, budget steps=10, TranscriptBus
  └─ research_agent [claude-haiku-5-5]: searches the notes and reports what they say.
       harness: StandardLoop, budget steps=5, GuardBus(TranscriptBus)
       tools: search_notes
```

The transcript shows the nested run, including the guard at work:

```text
[writer_agent] → research_agent(task='Find what the notes say about the budget.')
    [research_agent] → search_notes(word='budget', limit=10)
    [research_agent] ⚑ guard: search_notes limit=10 is out of range, changed to 2
    [research_agent] ← search_notes: The budget limits steps, tokens, cost and time. A run stops when the mod…
    [research_agent] ■ done (end_turn)
[writer_agent] ← research_agent: The budget limits steps, tokens, cost and time. A run stops when the model a…
[writer_agent] ■ done (end_turn)
```

### 5. Running offline

`PlaybookModel` replaces a real model with a script, chosen by a keyword in the task. Each turn either calls tools (a list of calls runs in parallel) or answers, and an answer can be built from the tool results so far. This makes agents testable without an API key:

```python
from modular_agents.composites.model.playbook_model import PlaybookModel, call, say

research_model = PlaybookModel(ref="playbook:research", playbooks={
    "budget": [
        call("search_notes", word="budget", limit=10),
        say(lambda results: results[-1]),
    ],
})
writer_model = PlaybookModel(ref="playbook:writer", playbooks={
    "summary": [
        call("research_agent", task="Find what the notes say about the budget."),
        say(lambda results: f"Summary: {results[-1]}"),
    ],
})
```

With `research_model` and `writer_model` passed as the `model` of the two blueprints above, the same run works with no network access.

### Defaults

A model is the only required part of an agent. Without a harness, `ComposedAgent` uses the standard loop, a limit of 25 steps per run and no tools:

```python
chat_agent = ComposedAgent(model=AnthropicModel(ref="claude-sonnet-5-5"))
```

## Examples

The [`examples/`](examples) directory has complete agents. They are not part of the installed package and run from a clone of the repository:

```sh
git clone https://github.com/frycz/modular-agents
cd modular-agents
uv sync
```

### Toy agents

The toy agents show that tools do not have to be files, shells or web services: an agent can just as well operate machines. Each toy operates simulated devices, plain Python objects that hold some state, such as an espresso machine with a boiler temperature or a thermostat with a target temperature. A device class marks its methods with `@action`, and each marked method becomes a tool: its docstring is the description and its parameters are the input schema. Every device also gets a read-only `status` tool. The `Device` class and `DeviceToolSet` live in `src/modular_agents/composites/devices/`.

```python
from modular_agents.composites.devices.device import Device, action


class CoffeeMachine(Device):
    name = "coffee"
    description = "the kitchen espresso machine"

    def __init__(self):
        self.boiler_c = 20

    @action
    def heat(self, celsius: int) -> str:
        """Heat the boiler to a temperature in °C."""
        self.boiler_c = celsius
        return f"boiler at {celsius}°C"
```

Because the state lives in the device and not in any agent's conversation, several agents can operate the same devices and see each other's changes.

The toy agents form a tree: a barista agent runs a coffee machine, a smart home agent uses the barista agent as a tool, a power plant agent calls in an inspector agent, and a city agent uses two smart home agents and the power plant agent. They run offline with playbook models:

```sh
uv run python -m examples.toys coffee
uv run python -m examples.toys city
```

With `--real` they all share one Claude model, read from `ANTHROPIC_MODEL` and `ANTHROPIC_API_KEY`, for example from `.env`:

```sh
uv run --env-file .env python -m examples.toys home --real
```

### Demo agent

The demo agent runs shell commands, reads and writes files, and can hand tasks to sub-agents. It brings its own tools, context policy, run store and event bus, and saves every run to `.runs/<id>.json`:

```sh
uv run --env-file .env python -m examples.demo "<task>" [effort]
```

### Simple agent

`examples/simple_agent/` is an agent with only a model, everything else left to its default, as a builder function.

## Project layout

`src/modular_agents/interfaces/`: the interfaces and the data types between them, one file per concept, with no implementations.

`src/modular_agents/composites/`: the ready building blocks that implement those interfaces.

`examples/`: agents composed from those blocks.

`tests/`: tests that use scripted models and make no API calls. `tests/test_boundaries.py` checks that the package never depends on the examples.

## Development

```sh
uv sync
uv run pytest
```

The documentation is built with MkDocs. Every code example in it is a file in `docs/examples/`, run by `tests/test_docs_examples.py`. To preview the site locally:

```sh
uv sync --group docs
uv run mkdocs serve
```

## License

MIT, see [LICENSE](LICENSE).
