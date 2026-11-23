"""ShellRunner: runs commands as local processes. The one place that starts processes."""

from __future__ import annotations

import asyncio
import shlex

from modular_agents.composites.helpers import abortable
from modular_agents.interfaces.cancellation import AbortSignal, Cancelled
from modular_agents.interfaces.env import Environment
from modular_agents.interfaces.runner import CommandRunner, ExecResult


class ShellRunner(CommandRunner):
    async def run(
        self, env: Environment, command: str, signal: AbortSignal, stdin: bytes | None = None, timeout_ms: float = 60_000,
    ) -> ExecResult:
        proc = await asyncio.create_subprocess_shell(
            self._command_line(env, command), stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await abortable(asyncio.wait_for(proc.communicate(stdin), timeout_ms / 1000), signal)
        except TimeoutError:
            proc.kill()
            return ExecResult(-1, "", f"timed out after {timeout_ms}ms")
        except Cancelled:
            proc.kill()
            raise
        return ExecResult(proc.returncode, out.decode(errors="replace"), err.decode(errors="replace"))

    @staticmethod
    def _command_line(env: Environment, command: str) -> str:
        """The prefix gets the command as one quoted argument, so spaces and quotes survive e.g. ssh."""
        return f"{env.prefix} {shlex.quote(command)}" if env.prefix else command
