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

    def classify(self, message: str) -> IntentResult:
        text = str(message or "").strip().lower()
        if any(token in text for token in ("退款", "退钱", "refund", "售后")):
            return IntentResult("refund_dispute", "high", ["refund_keyword"])
        if any(token in text for token in ("法务", "律师", "起诉", "legal", "合同纠纷")):
            return IntentResult("legal_issue", "high", ["legal_keyword"])
        if any(token in text for token in ("付款", "转账", "银行卡", "pay", "payment", "打款")):
            return IntentResult("payment_sensitive", "high", ["payment_keyword"])
        if any(token in text for token in ("投诉", "差评", "不满意", "complaint")):
            return IntentResult("complaint", "high", ["complaint_keyword"])
        if any(token in text for token in ("多少钱", "价格", "报价", "price", "cost")):
            return IntentResult("price_inquiry", "low", ["price_keyword"])
        if any(token in text for token in ("你好", "您好", "hello", "hi")):
            return IntentResult("greeting", "low", ["greeting_keyword"])
        return IntentResult("general_inquiry", "medium", ["default_rule"])
