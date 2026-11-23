"""JsonRunStore: one JSON file per run."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from modular_agents.interfaces.state import RunState
from modular_agents.interfaces.store import RunStore


class JsonRunStore(RunStore):
    """Saves each run as a JSON file, so it can be inspected or resumed."""

    def __init__(self, directory: str = ".runs"):
        self.dir = Path(directory)

    async def save(self, state: RunState) -> None:
        self.dir.mkdir(exist_ok=True)
        (self.dir / f"{state.id}.json").write_text(json.dumps(asdict(state), indent=2))

    async def load(self, id: str) -> RunState | None:
        path = self.dir / f"{id}.json"
        return RunState(**json.loads(path.read_text())) if path.exists() else None
