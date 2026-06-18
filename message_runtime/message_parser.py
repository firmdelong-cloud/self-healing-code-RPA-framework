"""Parse raw chat text into normalized message metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedMessage:
    contact_name: str
    latest_message: str
    normalized_text: str
    is_group_chat: bool
    sender_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MessageParser:
    """Normalize message text before intent classification."""

    def parse(
        self,
        *,
        contact_name: str,
        latest_message: str,
        is_group_chat: bool = False,
    ) -> ParsedMessage:
        raw_text = str(latest_message or "").strip()
        sender_name: str | None = None
        normalized = raw_text

        if is_group_chat and ":" in raw_text:
            sender_part, message_part = raw_text.split(":", 1)
            sender_name = sender_part.strip() or None
            normalized = message_part.strip()

        return ParsedMessage(
            contact_name=str(contact_name or "").strip(),
            latest_message=raw_text,
            normalized_text=normalized,
            is_group_chat=is_group_chat,
            sender_name=sender_name,
        )
