"""Decision engine for event Skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Decision:
    """High-level event handling decision."""

    should_act: bool
    action_mode: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_act": self.should_act,
            "action_mode": self.action_mode,
            "reasons": list(self.reasons),
        }


class DecisionEngine:
    """Apply policy and context to decide the next event action."""

    def decide(self, *, event: dict[str, Any], context: dict[str, Any], policy: dict[str, Any]) -> Decision:
        if bool(context.get("already_handled")):
            return Decision(False, "skip", ["already_handled"])
        if bool(context.get("is_group_chat")) and not bool(policy.get("allow_group_chat", False)):
            return Decision(False, "skip", ["group_chat_blocked"])
        if bool(policy.get("draft_only", True)):
            return Decision(True, "draft", [])
        if bool(policy.get("auto_send", False)):
            return Decision(True, "send", [])
        return Decision(True, "draft", ["auto_send_disabled"])
