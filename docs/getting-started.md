# Getting started

This page installs the package, composes a first agent with one tool and runs it, first offline with a scripted model, then on Claude.

## Install

The Python implementation requires Python 3.12 or newer and depends only on `httpx`.

```sh
pip install modular-agents
```

Until the first release, the package is installed from GitHub:

```sh
pip install git+https://github.com/frycz/modular-agents
```

## A first agent

The agent answers questions about the weather. It needs four things: a tool, a model, a harness and the agent that joins them.

### The tool

A tool is a class with a `definition`, which the model sees, and an `execute()` method, which the loop calls with the input the model asked for. The result is returned as a `ToolOutput`, here built with the `text_output()` helper. Problems the model should know about, such as an unknown city, are returned as an error result instead of being raised.

```python
--8<-- "docs/examples/first_agent.py:tool"
```

`readonly` and `concurrent` are hints for the rest of the system: this tool only reads, so permission rules may allow it freely and the loop may run several calls of it in parallel.

### The model

`PlaybookModel` is a scripted model. It picks a playbook by a keyword in the task and plays one turn per model call: a list of tool calls (run in parallel) or an answer. It needs no network and no API key, which makes it the model of choice for tests and for this page.

```python
--8<-- "docs/examples/first_agent.py:model"
```

### The harness and the agent

The harness holds everything around the model. The loop and the budget are required, so every agent has a guaranteed end. The tools, the event bus and the other parts are optional. `TranscriptBus` prints each tool call and result.

```python
--8<-- "docs/examples/first_agent.py:agent"
```

### The run

`async with` starts the model and the tools before the first run and closes them after the last. `run()` adds the task to the agent's conversation and runs the loop until it stops.

```python
--8<-- "docs/examples/first_agent.py:run"
```

Output:

```text
[weather_agent] → get_forecast(city='Oslo')
[weather_agent] ← get_forecast: snow, -3°C
[weather_agent] → get_forecast(city='Lisbon')
[weather_agent] ← get_forecast: sunny, 19°C
[weather_agent] ■ done (end_turn)
end_turn
Oslo: snow, -3°C. Lisbon: sunny, 19°C.
```

The run took two model calls. In the first, the model asked for both forecasts at once, and the loop ran the two calls in parallel. In the second, the model answered, so the run ended with the stop reason `end_turn`.

## The same agent on Claude

Replacing the model is a change to one line. `AnthropicModel` calls the Anthropic Messages API and reads the API key from the `ANTHROPIC_API_KEY` environment variable:

```python
--8<-- "docs/examples/first_agent_claude.py:model"
```

```sh
export ANTHROPIC_API_KEY=...
python docs/examples/first_agent_claude.py
```

The tool, the harness and the agent stay exactly as they are. The complete file is [`docs/examples/first_agent_claude.py`](https://github.com/frycz/modular-agents/blob/main/docs/examples/first_agent_claude.py).

!!! note "Cost tracking"
    `AnthropicModel` does not know the prices of the models, so the cost it reports is 0 and a budget limit on `cost_usd` never stops it. To track cost, build the model from an endpoint with prices, as shown on the [Model](concepts/model.md#behind-the-interface) page, or limit tokens instead.

## Next steps

The [Concepts](concepts/index.md) pages explain every block used above and the ones not used yet: the context policy, the run store, custom event rules and composition. The [research team tutorial](tutorials/research-team.md) composes two agents where one uses the other as a tool.

All code on this site is taken from files in [`docs/examples/`](https://github.com/frycz/modular-agents/tree/main/docs/examples), which the test suite runs, so every example is known to work.
