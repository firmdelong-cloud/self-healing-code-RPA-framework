"""Experimental WeChat Event Skill adapter contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from event_runtime.event_detector import Event


@dataclass(frozen=True)
class WeChatAdapter:
    """Thin adapter facade for visible desktop WeChat automation.

    The adapter owns WeChat-specific sensing and actions. The event runtime only
    consumes normalized events and context.
    """

    window: Any
    vision: Any

    def list_unread_events(self, *, max_contacts: int = 5) -> list[Event]:
        unread_contacts = self.vision.find_unread_contacts(self.window, limit=max_contacts)
        events: list[Event] = []
        for contact in unread_contacts:
            contact_name = str(contact.get("contact_name", "")).strip()
            if not contact_name:
                continue
            events.append(
                Event(
                    event_id=f"wechat:{contact_name}:{contact.get('unread_count', 1)}",
                    event_type="unread_message",
                    subject_id=contact_name,
                    source="wechat",
                    payload=dict(contact),
                )
            )
        return events

    def read_context(self, *, history_turns: int) -> dict[str, Any]:
        turns = self.vision.read_chat_turns(self.window, limit=history_turns)
        latest_turn = turns[-1] if turns else None
        return {
            "turns": [
                {
                    "direction": turn.direction,
                    "text": turn.text,
                }
                for turn in turns
            ],
            "latest_turn": {
                "direction": latest_turn.direction,
                "text": latest_turn.text,
            }
            if latest_turn
            else None,
        }

    def draft_message(self, text: str) -> None:
        self.vision.fill_reply_text(self.window, text)

    def send_message(self) -> bool:
        return bool(self.vision.click_send(self.window))
