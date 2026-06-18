"""Conversation audit logging for desktop message Skills."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any


class ConversationLogger:
    """Write structured conversation events and query recent send counts."""

    def __init__(self, log_dir: Path, *, skill_id: str):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"{skill_id}.jsonl"

    def record(self, event_type: str, *, contact_name: str, payload: dict[str, Any]) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "contact_name": contact_name,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def count_sent_for_contact(self, contact_name: str, *, within_hours: int) -> int:
        return sum(
            1
            for event in self._recent_events(within_hours=within_hours)
            if event["event_type"] == "message_sent" and event["contact_name"] == contact_name
        )

    def count_sent_total(self, *, within_hours: int) -> int:
        return sum(1 for event in self._recent_events(within_hours=within_hours) if event["event_type"] == "message_sent")

    def looks_like_recent_reply_echo(self, contact_name: str, message_text: str, *, within_hours: int = 24) -> bool:
        normalized_message = self._normalize_text(message_text)
        if len(normalized_message) < 6:
            return False

        for event in self._recent_events(within_hours=within_hours):
            if event["contact_name"] != contact_name:
                continue
            reply_text = str(event.get("payload", {}).get("reply_text", "")).strip()
            normalized_reply = self._normalize_text(reply_text)
            if len(normalized_reply) < 6:
                continue
            if normalized_message == normalized_reply:
                return True
            if normalized_message.startswith(normalized_reply) or normalized_reply.startswith(normalized_message):
                return True
        return False

    def was_recent_message_handled(self, contact_name: str, message_text: str, *, within_hours: int = 24) -> bool:
        normalized_message = self._normalize_text(message_text)
        if len(normalized_message) < 6:
            return False

        for event in self._recent_events(within_hours=within_hours):
            if event["contact_name"] != contact_name:
                continue
            prior_message = str(event.get("payload", {}).get("latest_message", "")).strip()
            normalized_prior = self._normalize_text(prior_message)
            if len(normalized_prior) < 6:
                continue
            if normalized_message == normalized_prior:
                return True
            if normalized_message.startswith(normalized_prior) or normalized_prior.startswith(normalized_message):
                return True
        return False

    def _recent_events(self, *, within_hours: int) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            ts = datetime.fromisoformat(event["ts"])
            if ts >= cutoff:
                events.append(event)
        return events

    def _normalize_text(self, text: str) -> str:
        collapsed = re.sub(r"\s+", "", str(text or "").strip()).lower()
        return re.sub(r"[,.!?:;\"'`~\[\]\(\)<>]", "", collapsed)
