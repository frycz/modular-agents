# Examples

The repository's [`examples/`](https://github.com/frycz/modular-agents/tree/main/examples) directory holds complete agents composed from the building blocks. They are not part of the installed package and run from a clone of the repository:

```sh
git clone https://github.com/frycz/modular-agents
cd modular-agents
uv sync
```

## Toy agents

The toy agents show that tools do not have to be files, shells or web services: an agent can just as well operate machines. They run offline with playbook models, and with `--real` on Claude.

### Simulated devices

Each toy operates simulated devices: plain Python objects that hold some state, such as an espresso machine with a boiler temperature or a thermostat with a target temperature. A device class marks its methods with `@action`, and each marked method becomes a tool: its docstring is the description and its parameters are the input schema. Every device also gets a read-only `status` tool.

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

`DeviceToolSet(machine)` offers the actions of one or more devices as a tool set, and `DeviceToolSet(machine, readonly=True)` offers only the actions that look without touching. Because the state lives in the device and not in any agent's conversation, several agents can operate the same devices and see each other's changes. A device method that raises `ValueError`, for example a brew with a cold boiler, is reported to the model as an error result, and the model can recover.

`Device`, `DeviceToolSet` and `LiveStatusPolicy`, which shows the model the current state of the devices on every call, are in `modular_agents.composites.devices` and `modular_agents.composites.policy`.

### The tree of toys

The toy agents nest, each one using the previous ones as tools:

- `coffee_machine`: a barista agent that runs an espresso machine. A guard clamps the boiler temperature to 96°C.
- `smart_home`: a smart home agent with lights, blinds, a thermostat and a front door, plus the barista agent as a tool. A guard forbids unlocking the door and clamps the thermostat between 16°C and 24°C.
- `power_plant`: a power plant agent that ramps generators up and down, and calls in an inspector agent that can read the gauges but touch nothing.
- `city`: a city agent that uses two smart home agents and the power plant agent.

```sh
uv run python -m examples.toys coffee
uv run python -m examples.toys city
```

The runner prints the composition tree, the transcript of the run and what the whole tree spent. With `--real`, every agent in the tree shares one Claude model, read from `ANTHROPIC_MODEL` and `ANTHROPIC_API_KEY`, for example from a `.env` file:

```sh
uv run --env-file .env python -m examples.toys home --real
```

## Demo agent

`examples/demo_agent/` is a general-purpose agent that runs shell commands, reads and writes files, and can hand self-contained tasks to sub-agents through `spawn_agent`. It brings its own blocks:

- `BashTool`, `ReadFileTool` and `WriteFileTool`: tools that run as shell commands in an environment, through a `CommandRunner`. The same tool classes can target the local machine or, with a command prefix, a container or a remote machine.
- `TruncatingContextPolicy`: cuts long tool outputs in what the model sees.
- `JsonRunStore`: saves every run as a JSON file in `.runs/`.
- `LoggingEventBus`: logs every event to stderr and denies tools by name.

```sh
uv run --env-file .env python -m examples.demo "<task>" [effort]
```

The final answer goes to stdout and every run is saved to `.runs/<id>.json`.

!!! warning
    The demo agent runs the shell commands the model chooses, on the local machine, without asking. Run it in a directory and on a machine where that is acceptable.

## Simple agent

`examples/simple_agent/` is an agent with only a model, everything else left to its default, as a builder function.
