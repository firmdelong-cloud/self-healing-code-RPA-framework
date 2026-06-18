"""Generate deterministic replies from rule-based intents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReplyResult:
    reply_text: str
    template_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReplyEngine:
    """Return a controlled reply template for the current intent."""

    REPLIES = {
        "price_inquiry": (
            "您好，具体价格需要看您选择的产品规格，我可以先发您一份报价参考。",
            "price_inquiry_default",
        ),
        "greeting": (
            "您好，我在的，请告诉我您想了解的产品或服务信息。",
            "greeting_default",
        ),
        "general_inquiry": (
            "您好，我已经收到您的消息，我先帮您确认一下具体情况。",
            "general_inquiry_default",
        ),
        "refund_dispute": (
            "您好，这类售后问题我需要转给人工同事进一步处理。",
            "refund_handoff",
        ),
        "legal_issue": (
            "您好，这类问题需要转人工同事跟进处理。",
            "legal_handoff",
        ),
        "payment_sensitive": (
            "您好，涉及付款信息的问题需要人工同事进一步确认。",
            "payment_handoff",
        ),
        "complaint": (
            "您好，很抱歉给您带来不便，我先转给人工同事尽快处理。",
            "complaint_handoff",
        ),
    }

    def generate(self, *, intent: str, latest_message: str, contact_name: str) -> ReplyResult:
        reply_text, template_id = self.REPLIES.get(
            intent,
            self.REPLIES["general_inquiry"],
        )
        return ReplyResult(reply_text=reply_text, template_id=template_id)
