"""Cancellation: one signal crosses every async boundary of a run."""

from __future__ import annotations

import asyncio

type AbortSignal = asyncio.Event  # set it to cancel a run and its whole subtree


class Cancelled(Exception):
    """Raised when an AbortSignal is set."""
