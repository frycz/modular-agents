"""Tools that run as shell commands in an environment: bash, read_file, write_file."""

from __future__ import annotations

import posixpath
import shlex

from examples.demo_agent.tools.shell_runner import ShellRunner
from modular_agents.composites.tools.tool_helpers import schema, signal, text_output
from modular_agents.interfaces.env import Environment
from modular_agents.interfaces.model import ToolDefinition
from modular_agents.interfaces.runner import CommandRunner
from modular_agents.interfaces.tools import Tool, ToolContext, ToolOutput


class EnvTool(Tool):
    """One tool class, one instance per environment. Non-local instances get the environment in name and description."""

    name: str
    description: str
    input_schema: dict

    def __init__(self, env: Environment | None = None, runner: CommandRunner | None = None):
        self.env = env or Environment()
        self.runner = runner or ShellRunner()

    @property
    def definition(self) -> ToolDefinition:
        local = not self.env.prefix
        return {
            "name": self.name if local else f"{self.name}_{self.env.name}",
            "description": self.description if local else f"{self.description} Runs on: {self.env.description or self.env.name}.",
            "input_schema": self.input_schema,
        }

class BashTool(EnvTool):
    name = "bash"
    description = "Run a shell command and return its exit code and output."
    input_schema = schema(command="The command to run.")

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        r = await self.runner.run(self.env, input["command"], signal(ctx))
        stderr = f"\nstderr:\n{r.stderr}" if r.stderr else ""
        return text_output(f"exit code {r.exit_code}\n{r.stdout}{stderr}")


class ReadFileTool(EnvTool):
    name = "read_file"
    readonly = concurrent = True
    description = "Read a text file."
    input_schema = schema(path="Path relative to the working directory.")

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        r = await self.runner.run(self.env, f"cat -- {shlex.quote(input['path'])}", signal(ctx))
        return text_output(r.stdout) if r.exit_code == 0 else text_output(r.stderr, is_error=True)


class WriteFileTool(EnvTool):
    name = "write_file"
    description = "Create or overwrite a text file."
    input_schema = schema(path="Path relative to the working directory.", content="The full file content.")

    async def execute(self, input: dict, ctx: ToolContext | None = None) -> ToolOutput:
        path = shlex.quote(input["path"])
        directory = posixpath.dirname(input["path"])
        mkdir = f"mkdir -p -- {shlex.quote(directory)} && " if directory else ""
        r = await self.runner.run(self.env, f"{mkdir}cat > {path}", signal(ctx), stdin=input["content"].encode())
        if r.exit_code != 0:
            return text_output(r.stderr, is_error=True)
        return text_output(f"wrote {len(input['content'])} characters to {input['path']}")
