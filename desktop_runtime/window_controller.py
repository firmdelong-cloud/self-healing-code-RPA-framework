"""Window abstractions for desktop message Skills."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from vision_runtime import WeChatVision


class DesktopRuntimeError(RuntimeError):
    """Raised when the desktop runtime cannot operate the target window."""


@dataclass
class DesktopSession:
    window: Any
    closer: Any | None = None

    def close(self) -> None:
        if callable(self.closer):
            self.closer()


class MockDesktopWindow:
    """Playwright-backed mock chat window used by tests and demos."""

    CHAT_PANEL_SELECTOR = "#chat-panel"
    CHAT_TITLE_SELECTOR = "#chat-title"
    SEND_STATUS_SELECTOR = "#send-status"
    REPLY_INPUT_SELECTOR = "#reply-box"

    def __init__(self, page: Any):
        self.page = page

    @property
    def url(self) -> str:
        return str(getattr(self.page, "url", "about:blank"))

    def open(self, url: str) -> None:
        self.page.goto(url)

    def detect_unread(self, selector: str) -> dict[str, Any]:
        item = self._first(selector)
        return self._contact_from_item(item)

    def click_chat(self, selector: str) -> dict[str, Any]:
        item = self._first(selector)
        item.click()
        self._wait_small()
        return {
            "contact_name": self.page.text_content(self.CHAT_TITLE_SELECTOR) or "",
            "is_group_chat": self.page.get_attribute(self.CHAT_PANEL_SELECTOR, "data-is-group") == "true",
        }

    def read_chat_text(self, selector: str) -> str:
        locator = self.page.locator(selector)
        if locator.count() == 0:
            raise DesktopRuntimeError(f"chat message selector not found: {selector}")
        return locator.last.inner_text().strip()

    def fill_text(self, selector: str, value: str) -> None:
        self.page.fill(selector, value)

    def send_message(self, selector: str) -> bool:
        self.page.click(selector)
        self._wait_small()
        status = self.page.text_content(self.SEND_STATUS_SELECTOR) or ""
        return "sent" in status.lower()

    def screenshot(self, path: str) -> None:
        self.page.screenshot(path=path, full_page=True)

    def content(self) -> str:
        return self.page.content()

    def state(self) -> dict[str, Any]:
        unread_contacts = self.page.locator(".contact-item.unread")
        return {
            "url": self.url,
            "current_contact": (self.page.text_content(self.CHAT_TITLE_SELECTOR) or "").strip(),
            "is_group_chat": self.page.get_attribute(self.CHAT_PANEL_SELECTOR, "data-is-group") == "true",
            "latest_message": self._safe_text("#chat-history .message.incoming .message-text:last-child"),
            "draft_text": self._safe_input_value(self.REPLY_INPUT_SELECTOR),
            "send_status": self._safe_text(self.SEND_STATUS_SELECTOR),
            "unread_contacts": unread_contacts.count(),
        }

    def _first(self, selector: str) -> Any:
        locator = self.page.locator(selector)
        if locator.count() == 0:
            raise DesktopRuntimeError(f"window selector not found: {selector}")
        return locator.first

    def _contact_from_item(self, item: Any) -> dict[str, Any]:
        name = item.get_attribute("data-contact-name") or item.locator(".contact-name").inner_text()
        unread_count = item.get_attribute("data-unread-count") or "1"
        is_group_chat = item.get_attribute("data-is-group") == "true"
        return {
            "contact_name": str(name).strip(),
            "unread_count": int(unread_count),
            "is_group_chat": is_group_chat,
        }

    def _safe_text(self, selector: str) -> str:
        locator = self.page.locator(selector)
        if locator.count() == 0:
            return ""
        return locator.last.inner_text().strip()

    def _safe_input_value(self, selector: str) -> str:
        locator = self.page.locator(selector)
        if locator.count() == 0:
            return ""
        return locator.input_value()

    def _wait_small(self) -> None:
        if hasattr(self.page, "wait_for_timeout"):
            self.page.wait_for_timeout(50)


class LiveWechatWindow:
    """Experimental Windows UI Automation adapter for the official desktop client.

    This adapter stays outside the stable Procedure Skill repair model. It is a
    best-effort desktop boundary that should be used only with explicit user
    control and conservative policies.
    """

    def __init__(self, window: Any):
        self.window = window
        self.vision = WeChatVision()
        self._last_contact_hint: dict[str, Any] | None = None

    @property
    def url(self) -> str:
        return "desktop://wechat"

    def open(self, url: str) -> None:
        self.window.set_focus()

    def detect_unread(self, selector: str) -> dict[str, Any]:
        contact = self._find_unread_contact()
        if contact is None:
            contact = self.vision.find_unread_contact(self.window)
        if contact is None:
            contact = self.vision.find_active_contact(self.window)
        if contact is None:
            raise DesktopRuntimeError("no unread WeChat conversation found")
        self._last_contact_hint = contact
        return contact

    def click_chat(self, selector: str) -> dict[str, Any]:
        contact = self._last_contact_hint or self._find_unread_contact()
        if contact is None:
            contact = self.vision.find_unread_contact(self.window) or self.vision.find_active_contact(self.window)
        if contact is None:
            raise DesktopRuntimeError("no unread WeChat conversation available to open")

        if contact.get("_element") is not None:
            element = contact["_element"]
            element.click_input()
        elif contact.get("click_point") is not None:
            from pywinauto import mouse

            click_x, click_y = contact["click_point"]
            rect = self.window.rectangle()
            mouse.click(coords=(int(rect.left + click_x), int(rect.top + click_y)))
        return {
            "contact_name": contact["contact_name"],
            "is_group_chat": contact["is_group_chat"],
        }

    def read_chat_text(self, selector: str) -> str:
        try:
            return self.vision.read_latest_incoming_message(self.window)
        except Exception:
            pass

        texts = [
            element.window_text().strip()
            for element in self.window.descendants(control_type="Text")
            if element.window_text().strip()
        ]
        if not texts:
            raise DesktopRuntimeError("unable to read chat text from WeChat window")
        return texts[-1]

    def fill_text(self, selector: str, value: str) -> None:
        try:
            editor = self._find_editor()
            editor.set_focus()
            editor.set_edit_text(str(value))
            return
        except Exception:
            self.vision.fill_reply_text(self.window, str(value))

    def send_message(self, selector: str) -> bool:
        try:
            button = self.window.child_window(title_re="Send|发送", control_type="Button")
            if button.exists():
                button.click_input()
                return True
        except Exception:
            pass
        return self.vision.click_send(self.window)

    def screenshot(self, path: str) -> None:
        image = self.window.capture_as_image()
        image.save(path)

    def content(self) -> str:
        texts = [element.window_text().strip() for element in self.window.descendants() if element.window_text().strip()]
        return "\n".join(texts)

    def state(self) -> dict[str, Any]:
        contact = self._last_contact_hint or self._find_unread_contact() or self.vision.find_active_contact(self.window)
        return {
            "url": self.url,
            "current_contact": contact["contact_name"] if contact else "",
            "is_group_chat": contact["is_group_chat"] if contact else False,
        }

    def _find_unread_contact(self) -> dict[str, Any] | None:
        candidates = []
        for item in self.window.descendants(control_type="ListItem"):
            text = item.window_text().strip()
            if not text:
                continue
            match = re.search(r"(\d+)$", text)
            if match:
                contact_name = text[: match.start()].strip(" ()")
                candidates.append(
                    {
                        "contact_name": contact_name or text,
                        "unread_count": int(match.group(1)),
                        "is_group_chat": "group" in text.lower() or "群" in text,
                        "_element": item,
                    }
                )
        if candidates:
            return candidates[0]
        return None

    def _find_editor(self) -> Any:
        editors = self.window.descendants(control_type="Edit")
        if not editors:
            raise DesktopRuntimeError("reply editor not found in WeChat window")
        return editors[-1]
