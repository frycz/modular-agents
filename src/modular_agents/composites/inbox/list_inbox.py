"""ListInbox: an in-memory inbox for one agent."""

from __future__ import annotations

from modular_agents.interfaces.inbox import Inbox
from modular_agents.interfaces.messages import ContentBlock


class ListInbox(Inbox):
    def __init__(self):
        self.waiting: list[ContentBlock] = []

    def put(self, content: list[ContentBlock]) -> None:
        self.waiting.extend(content)

    def take(self) -> list[ContentBlock]:
        taken, self.waiting = self.waiting, []
        return taken
