"""Event detection contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    """A normalized event emitted by an adapter."""

    event_id: str
    event_type: str
    subject_id: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventDetector(Protocol):
    """Adapter-facing detector protocol."""

    def detect(self) -> list[Event]:
        """Return currently visible or available events."""
