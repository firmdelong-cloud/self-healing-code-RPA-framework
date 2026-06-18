"""Safety checks before a desktop message can be auto-sent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    handoff_required: bool
    reasons: list[str]
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafetyGuard:
    """Block high-risk intents from unattended auto-send."""

    def evaluate(self, *, intent: str, latest_message: str, policy: dict[str, Any]) -> SafetyDecision:
        blocked_intents = {str(item) for item in policy.get("blocked_intents", [])}
        if intent in blocked_intents:
            return SafetyDecision(
                allowed=False,
                handoff_required=bool(policy.get("fallback_to_human", True)),
                reasons=[f"intent_blocked:{intent}"],
                risk_level="high",
            )

        return SafetyDecision(
            allowed=True,
            handoff_required=False,
            reasons=[],
            risk_level="low",
        )
