"""Command runner: runs a shell command in an environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .cancellation import AbortSignal
from .env import Environment


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class CommandRunner(ABC):
    @abstractmethod
    async def run(
        self, env: Environment, command: str, signal: AbortSignal, stdin: bytes | None = None, timeout_ms: float = 60_000,
    ) -> ExecResult: ...
