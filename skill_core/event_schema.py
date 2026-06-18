"""Schema loader for event-driven automation Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .policy import SafetyPolicy
from .skill_schema import SkillKind, normalize_skill_kind


class EventSkillSchemaError(ValueError):
    """Raised when an event Skill declaration is invalid."""


@dataclass(frozen=True)
class EventSkillDefinition:
    """Declarative event Skill contract.

    Event Skills are not fixed step lists. They describe how to observe events,
    build context, decide whether to act, and choose a safe action mode.
    """

    id: str
    name: str
    version: str
    runtime: str
    base_path: Path
    trigger: dict[str, Any]
    observe: dict[str, Any]
    decision_policy: dict[str, Any]
    reply_policy: dict[str, Any]
    rate_limit: dict[str, Any]
    safety: SafetyPolicy
    memory: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> "EventSkillDefinition":
        skill_path = Path(path).resolve()
        if not skill_path.exists():
            raise EventSkillSchemaError(f"Event Skill file does not exist: {skill_path}")

        raw = yaml.safe_load(skill_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise EventSkillSchemaError("event_skill.yaml root must be a mapping")

        kind = normalize_skill_kind(raw.get("type"))
        if kind != SkillKind.EVENT:
            raise EventSkillSchemaError("event_skill.yaml must declare type: event_skill")

        missing = [
            key
            for key in [
                "id",
                "name",
                "version",
                "runtime",
                "trigger",
                "observe",
                "decision_policy",
                "reply_policy",
                "rate_limit",
                "safety",
            ]
            if key not in raw
        ]
        if missing:
            raise EventSkillSchemaError(f"Event Skill is missing required fields: {missing}")

        return cls(
            id=str(raw["id"]),
            name=str(raw["name"]),
            version=str(raw["version"]),
            runtime=str(raw["runtime"]),
            base_path=skill_path.parent,
            trigger=_mapping(raw, "trigger"),
            observe=_mapping(raw, "observe"),
            decision_policy=_mapping(raw, "decision_policy"),
            reply_policy=_mapping(raw, "reply_policy"),
            rate_limit=_mapping(raw, "rate_limit"),
            safety=SafetyPolicy.from_mapping(_mapping(raw, "safety")),
            memory=_mapping(raw, "memory") if "memory" in raw else {},
            raw=raw,
        )


def _mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise EventSkillSchemaError(f"event_skill.yaml field '{key}' must be a mapping")
    return value
