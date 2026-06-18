"""Policy checks for controlled auto-send behavior."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .conversation_logger import ConversationLogger
from .safety_guard import SafetyDecision


@dataclass(frozen=True)
class AutoSendDecision:
    allowed: bool
    handoff_required: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoSendPolicy:
    """Decide whether the generated reply may be auto-sent."""

    def evaluate(
        self,
        *,
        contact_name: str,
        is_group_chat: bool,
        policy: dict[str, Any],
        logger: ConversationLogger,
        safety_decision: SafetyDecision,
    ) -> AutoSendDecision:
        reasons: list[str] = []
        handoff_required = False

        if not bool(policy.get("auto_send", False)):
            reasons.append("auto_send_disabled")
            handoff_required = bool(policy.get("fallback_to_human", True))

        if not safety_decision.allowed:
            reasons.extend(safety_decision.reasons)
            handoff_required = handoff_required or safety_decision.handoff_required

        if is_group_chat and not bool(policy.get("allow_group_chat", False)):
            reasons.append("group_chat_blocked")
            handoff_required = handoff_required or bool(policy.get("fallback_to_human", True))

        if logger.count_sent_for_contact(contact_name, within_hours=1) >= int(
            policy.get("max_replies_per_contact_per_hour", 3)
        ):
            reasons.append("contact_hourly_limit_reached")
            handoff_required = handoff_required or bool(policy.get("fallback_to_human", True))

        if logger.count_sent_total(within_hours=1) >= int(policy.get("max_total_replies_per_hour", 20)):
            reasons.append("global_hourly_limit_reached")
            handoff_required = handoff_required or bool(policy.get("fallback_to_human", True))

        return AutoSendDecision(
            allowed=not reasons,
            handoff_required=handoff_required,
            reasons=reasons,
        )
