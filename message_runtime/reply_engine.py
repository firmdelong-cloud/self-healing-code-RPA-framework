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
    """Return a controlled reply template for the current intent.

    The message runtime intentionally stays rule-based in this repository.
    External LLM/API reply generation can be added later behind the same
    interface, but tests and default demos must remain deterministic.
    """

    REPLIES = {
        "price_inquiry": (
            "Hello, the exact price depends on the product specification. "
            "I can share a quotation reference first.",
            "price_inquiry_default",
        ),
        "greeting": (
            "Hello, I am here. Please tell me which product or service you want to know about.",
            "greeting_default",
        ),
        "general_inquiry": (
            "Hello, I have received your message. I will confirm the details first.",
            "general_inquiry_default",
        ),
        "refund_dispute": (
            "Hello, this after-sale issue needs a human colleague to follow up.",
            "refund_handoff",
        ),
        "legal_issue": (
            "Hello, this legal issue needs a human colleague to follow up.",
            "legal_handoff",
        ),
        "payment_sensitive": (
            "Hello, payment-related information needs human confirmation.",
            "payment_handoff",
        ),
        "complaint": (
            "Hello, sorry for the inconvenience. I will hand this over to a human colleague.",
            "complaint_handoff",
        ),
    }

    WAIT_KEYWORDS = {"wait", "later", "hold on", "afternoon", "tomorrow"}
    PRICE_CONTEXT_KEYWORDS = {"price", "quote", "quotation", "cost", "how much"}

    def generate(
        self,
        *,
        intent: str,
        latest_message: str,
        contact_name: str,
        recent_history: list[dict[str, str]] | None = None,
    ) -> ReplyResult:
        history_text = " ".join(item.get("text", "") for item in (recent_history or []))
        normalized_latest = str(latest_message or "").strip()
        normalized_history = f"{history_text} {normalized_latest}".strip()

        if self._contains_any(normalized_latest, self.WAIT_KEYWORDS) and normalized_history:
            return ReplyResult(
                reply_text=(
                    "No problem. I will keep following this conversation, and you can send any new "
                    "details when you are ready."
                ),
                template_id="wait_followup_contextual",
            )

        if intent == "general_inquiry" and self._contains_any(
            normalized_history,
            self.PRICE_CONTEXT_KEYWORDS,
        ):
            return ReplyResult(
                reply_text=(
                    "Got it. I see the price context, so I will organize a clear quotation reference "
                    "for you."
                ),
                template_id="price_followup_contextual",
            )

        reply_text, template_id = self.REPLIES.get(intent, self.REPLIES["general_inquiry"])
        return ReplyResult(reply_text=reply_text, template_id=template_id)

    def _contains_any(self, text: str, keywords: set[str]) -> bool:
        haystack = str(text or "").lower()
        return any(keyword.lower() in haystack for keyword in keywords)
