"""Inbox: content that arrives while a run is going, e.g. a message typed by the user or a background task's result."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .messages import ContentBlock


class Inbox(ABC):
    @abstractmethod
    def put(self, content: list[ContentBlock]) -> None:
        """Called from outside the loop: the UI, a background task."""

    @abstractmethod
    def take(self) -> list[ContentBlock]:
        """Everything waiting, in order; the inbox is empty afterwards. The loop calls it between steps."""
