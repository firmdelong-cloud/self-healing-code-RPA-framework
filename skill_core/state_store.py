"""Small persistent state store used by event Skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStateStore:
    """Persist small event runtime state as JSON files under storage/state."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, namespace: str) -> dict[str, Any]:
        path = self._path(namespace)
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data

    def save(self, namespace: str, state: dict[str, Any]) -> Path:
        path = self._path(namespace)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _path(self, namespace: str) -> Path:
        safe_name = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in namespace)
        return self.root / f"{safe_name}.json"
