"""Action policy for event Skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionDecision:
    """Outcome of an event action policy."""

    allowed: bool
    action_mode: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action_mode": self.action_mode,
            "reason": self.reason,
        }


class ActionPolicy:
    """Choose whether an event should become a draft, confirmation, or send."""

    def evaluate(self, *, decision: Any, policy: dict[str, Any]) -> ActionDecision:
        if decision.action_mode == "skip":
            return ActionDecision(False, "skip", reason="decision_skipped")
        if bool(policy.get("require_human_confirm", False)):
            return ActionDecision(True, "confirm", reason="human_confirmation_required")
        if decision.action_mode == "send":
            return ActionDecision(True, "send")
        return ActionDecision(True, "draft")
