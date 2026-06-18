"""Read chat state from a desktop window abstraction."""

from __future__ import annotations

from typing import Any


def detect_unread(window: Any, selector: str) -> dict[str, Any]:
    return window.detect_unread(selector)


def read_chat_text(window: Any, selector: str) -> str:
    return window.read_chat_text(selector)
