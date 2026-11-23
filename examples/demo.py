"""CLI: build a concrete agent, then run a task."""

from __future__ import annotations

import asyncio
import os
import sys

from examples.demo_agent import build_agent, message_text


def main() -> None:
    """Usage: uv run python -m examples.demo "your task" [effort]"""
    if len(sys.argv) < 2:
        sys.exit(main.__doc__)
    agent = build_agent(os.environ["ANTHROPIC_MODEL"], os.environ["ANTHROPIC_API_KEY"], sys.argv[2] if len(sys.argv) > 2 else None)

    async def run():
        async with agent:  # starts and closes the model's HTTP client and the tools
            return await agent.run(sys.argv[1])

    print(message_text(asyncio.run(run()).final))


if __name__ == "__main__":
    main()
