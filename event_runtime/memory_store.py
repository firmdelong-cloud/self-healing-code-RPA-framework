"""Persistent state for event Skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EventMemoryStore:
    """Store small event state snapshots as JSON."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, event_id: str) -> dict[str, Any]:
        path = self._path(event_id)
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def save(self, event_id: str, state: dict[str, Any]) -> Path:
        path = self._path(event_id)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def mark_handled(self, event_id: str, payload: dict[str, Any] | None = None) -> Path:
        state = self.load(event_id)
        state.update({
            "handled": True,
            "payload": payload or {},
        })
        return self.save(event_id, state)

    def _path(self, event_id: str) -> Path:
        safe_name = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in event_id)
        return self.root / f"{safe_name}.json"
