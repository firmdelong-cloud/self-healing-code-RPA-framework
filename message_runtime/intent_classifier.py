"""Rule-based intent classification for desktop message automation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IntentResult:
    intent: str
    risk_level: str
    matched_rules: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntentClassifier:
    """Classify common customer-service intents without calling an LLM."""

    REFUND_KEYWORDS = {
        "refund",
        "return money",
        "cancel order",
        "after-sale",
    }
    LEGAL_KEYWORDS = {
        "legal",
        "lawyer",
        "lawsuit",
        "contract dispute",
    }
    PAYMENT_KEYWORDS = {
        "payment",
        "pay",
        "bank card",
        "transfer",
        "account number",
    }
    COMPLAINT_KEYWORDS = {
        "complaint",
        "bad review",
        "not satisfied",
        "angry",
    }
    PRICE_KEYWORDS = {
        "price",
        "quote",
        "quotation",
        "cost",
        "how much",
    }
    GREETING_KEYWORDS = {
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
    }

    def classify(self, message: str) -> IntentResult:
        text = str(message or "").strip().lower()
        if self._contains_any(text, self.REFUND_KEYWORDS):
            return IntentResult("refund_dispute", "high", ["refund_keyword"])
        if self._contains_any(text, self.LEGAL_KEYWORDS):
            return IntentResult("legal_issue", "high", ["legal_keyword"])
        if self._contains_any(text, self.PAYMENT_KEYWORDS):
            return IntentResult("payment_sensitive", "high", ["payment_keyword"])
        if self._contains_any(text, self.COMPLAINT_KEYWORDS):
            return IntentResult("complaint", "high", ["complaint_keyword"])
        if self._contains_any(text, self.PRICE_KEYWORDS):
            return IntentResult("price_inquiry", "low", ["price_keyword"])
        if self._contains_any(text, self.GREETING_KEYWORDS):
            return IntentResult("greeting", "low", ["greeting_keyword"])
        return IntentResult("general_inquiry", "medium", ["default_rule"])

    def _contains_any(self, text: str, keywords: set[str]) -> bool:
        return any(keyword in text for keyword in keywords)
