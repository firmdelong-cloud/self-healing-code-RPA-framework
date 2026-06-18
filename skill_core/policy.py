"""Shared safety policy helpers for automation Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SafetyPolicy:
    """Common high-level safety boundaries used by event and procedure runtimes."""

    block_high_risk_intents: bool = True
    block_payment: bool = True
    block_private_sensitive: bool = True
    require_human_confirm: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "SafetyPolicy":
        raw = dict(data or {})
        known = {
            "block_high_risk_intents",
            "block_payment",
            "block_private_sensitive",
            "require_human_confirm",
        }
        return cls(
            block_high_risk_intents=bool(raw.get("block_high_risk_intents", True)),
            block_payment=bool(raw.get("block_payment", True)),
            block_private_sensitive=bool(raw.get("block_private_sensitive", True)),
            require_human_confirm=bool(raw.get("require_human_confirm", False)),
            extra={key: value for key, value in raw.items() if key not in known},
        )
