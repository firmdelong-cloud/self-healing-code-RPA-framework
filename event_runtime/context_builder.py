"""Context building for event Skills."""

from __future__ import annotations

from typing import Any, Protocol

from .event_detector import Event


class ContextBuilder(Protocol):
    """Build contextual evidence before an Event Skill makes a decision."""

    def build(self, event: Event) -> dict[str, Any]:
        """Return normalized context for the event."""
