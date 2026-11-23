# Budget

The budget is the stop condition of a run: how many steps, tokens, dollars and milliseconds it may use. Every harness has one, so every agent has a guaranteed end, even when the model never stops calling tools.

## The interface

```python
class Budget(ABC):
    def remaining(self) -> BudgetState: ...
    def charge(self, usage: Usage) -> None: ...  # also charged to all ancestors
    def child(self, limit: BudgetLimit) -> Budget: ...  # capped by the remaining parent budget


class BudgetLimit(TypedDict, total=False):
    steps: float
    tokens: float
    cost_usd: float
    elapsed_ms: float
```

The loop charges the usage of every model call to the budget and checks `remaining()` before each step: when any amount reaches zero, the run stops with `budget_exhausted`. A step is one model call. Tokens count input, output and cache tokens together.

`child()` creates a budget for a sub-agent. The child has its own limit, but it can never use more than its parent has left, and everything it spends is charged to the parent too.

## Tree budget

`TreeBudget` implements the interface. A limit left out of `BudgetLimit` means no limit on that amount.

```python
--8<-- "docs/examples/budget.py:tree"
```

Output:

```text
parent spent: {'steps': 1, 'tokens': 2000, 'cost_usd': 0.0, 'elapsed_ms': 900.0}
child left: {'steps': 2, 'tokens': 3000, 'cost_usd': inf, 'elapsed_ms': inf}
```

The child's own limit was 3 steps and no tokens limit, but it sees only the 3000 tokens its parent has left. Budgets nested this way form a tree, and a limit on the top agent covers every agent below it, so a runaway sub-agent cannot use up its parent.

## A run that hits its limit

A model that never stops calling tools, under a limit of 3 steps:

```python
--8<-- "docs/examples/budget.py:exhausted"
```

Output:

```text
budget_exhausted after 7 messages
```

The run stopped after three model calls: the task, three tool calls and three results make seven messages.

## Limits per run and per session

The budget in the harness is the limit of each run: every `run()` of an [agent](agent.md) gets a fresh child of it. A session budget, given to the agent, limits all its runs together:

```python
--8<-- "docs/examples/budget.py:session"
```

Output:

```text
run 1: budget_exhausted, session spent 3 steps
run 2: budget_exhausted, session spent 4 steps
run 3: budget_exhausted, session spent 4 steps
```

The first run used its 3 steps. The second run could take only 1 step, because the session had 1 left, and the third could take none.

## Cost

The cost of a call is filled in by the model. A model built on an endpoint with prices reports the real cost, and a `cost_usd` limit then works. `AnthropicModel` and `PlaybookModel` report costs that do not reflect real prices, as described on the [Model](model.md#endpoint-and-scheduler) page.
