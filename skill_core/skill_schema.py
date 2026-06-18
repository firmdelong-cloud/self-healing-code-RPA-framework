"""Shared Skill type helpers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class SkillSchemaError(ValueError):
    """Raised when a Skill declaration does not match the core schema."""


class SkillKind(StrEnum):
    """Supported top-level automation Skill models."""

    PROCEDURE = "procedure_skill"
    EVENT = "event_skill"


def normalize_skill_kind(raw: Any) -> SkillKind:
    """Return the declared Skill kind, defaulting old Skills to procedure_skill."""

    value = str(raw or SkillKind.PROCEDURE.value).strip()
    try:
        return SkillKind(value)
    except ValueError as error:
        allowed = ", ".join(kind.value for kind in SkillKind)
        raise SkillSchemaError(f"Unsupported Skill type '{value}'. Allowed values: {allowed}") from error
