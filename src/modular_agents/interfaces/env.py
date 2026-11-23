"""Environment: where environment-bound tools run their commands. Plain data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Environment:
    name: str = "local"  # "local", "raspi"; non-local environments add it to their tool names
    prefix: str = ""  # runs the quoted command, e.g. "ssh pi@raspi" or "docker exec -i box sh -c"; empty runs it locally
    description: str = ""  # tells the model where the tools run, e.g. "Raspberry Pi over SSH"
