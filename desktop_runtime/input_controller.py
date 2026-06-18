"""Write text and send messages through a desktop window abstraction."""

from __future__ import annotations

from typing import Any


def fill_text(window: Any, selector: str, value: str) -> None:
    window.fill_text(selector, value)


def send_message(window: Any, selector: str) -> bool:
    return bool(window.send_message(selector))
