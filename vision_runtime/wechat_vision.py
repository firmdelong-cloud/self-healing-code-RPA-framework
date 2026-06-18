"""Vision fallback for visible desktop chat windows.

This module is intentionally best-effort and experimental. It does not use
protocol reverse engineering, hooks, injection, or hidden control. Stable
production message automations should be modeled as Event Skills with explicit
human-confirm or draft-only policies.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any

import cv2
import numpy as np

from .ocr_reader import OCRLine, RapidOcrReader


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[int, int]:
        return (self.x1 + self.width // 2, self.y1 + self.height // 2)


@dataclass(frozen=True)
class ChatTurn:
    direction: str
    text: str
    y1: int
    y2: int


class WeChatVision:
    """Best-effort visual analysis for Qt-style desktop chat windows."""

    TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
    DATE_HINT_RE = re.compile(
        r"^(?:yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{2}/\d{2})$",
        re.IGNORECASE,
    )

    def __init__(self, ocr_reader: Any | None = None) -> None:
        self.ocr_reader = ocr_reader or RapidOcrReader()

    def find_unread_contact(self, window: Any) -> dict[str, Any] | None:
        contacts = self.find_unread_contacts(window, limit=1)
        return contacts[0] if contacts else None

    def find_unread_contacts(self, window: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
        image = self._capture(window)
        list_box = self._conversation_list_box(image)
        unread_rows = self._find_red_badge_rows(image, list_box)
        ocr_lines = self.ocr_reader.read(image)

        contacts: list[dict[str, Any]] = []
        for row_y in unread_rows:
            contact = self._contact_from_row(image, ocr_lines, list_box, row_y, unread_count=1)
            if self._looks_like_contact_name(contact["contact_name"]):
                contacts.append(contact)
                if limit is not None and len(contacts) >= limit:
                    break
        return contacts

    def read_unread_collection(self, window: Any) -> dict[str, Any] | None:
        image = self._capture(window)
        nav_box = self._chat_nav_badge_box(image)
        badge_boxes = self._find_red_component_boxes(image, nav_box, min_area=45)
        if not badge_boxes:
            return None

        badge_box = max(badge_boxes, key=lambda candidate: candidate.width * candidate.height)
        ocr_lines = self.ocr_reader.read(image)
        return {
            "has_unread": True,
            "count": self._extract_integer_from_box(ocr_lines, badge_box),
            "click_point": self._chat_nav_click_box(image).center,
            "badge_box": badge_box,
        }

    def find_active_contact(self, window: Any) -> dict[str, Any] | None:
        image = self._capture(window)
        list_box = self._conversation_list_box(image)
        active_row = self._find_selected_row(image, list_box)
        if active_row is None:
            return None
        ocr_lines = self.ocr_reader.read(image)
        return self._contact_from_row(image, ocr_lines, list_box, active_row, unread_count=0)

    def read_chat_turns(self, window: Any, *, limit: int = 8) -> list[ChatTurn]:
        image = self._capture(window)
        chat_box = self._chat_history_box(image)
        ocr_lines = self.ocr_reader.read(image)
        chat_lines = [
            line
            for line in ocr_lines
            if self._intersects(line, chat_box) and not self._is_time_like(line.text)
        ]
        chat_lines.sort(key=lambda line: (line.cy, line.x1))
        turns = self._group_chat_turns(chat_lines, chat_box)
        return turns[-limit:]

    def read_latest_incoming_message(self, window: Any) -> str:
        turns = self.read_chat_turns(window, limit=12)
        for turn in reversed(turns):
            if turn.direction == "incoming":
                return turn.text
        raise RuntimeError("no incoming message found in the current chat history")

    def fill_reply_text(self, window: Any, text: str) -> None:
        from pywinauto import mouse
        from pywinauto.keyboard import send_keys

        image = self._capture(window)
        input_box = self._input_box(image)
        abs_point = self._absolute_point(window, input_box.center)
        window.set_focus()
        time.sleep(0.05)
        mouse.click(coords=abs_point)
        time.sleep(0.05)
        self._set_clipboard_text(text)
        send_keys("^a{BACKSPACE}")
        time.sleep(0.02)
        send_keys("^v")

    def read_input_text(self, window: Any) -> str:
        image = self._capture(window)
        text_box = self._input_text_box(image)
        ocr_lines = self.ocr_reader.read(image)
        lines = [
            line.text
            for line in ocr_lines
            if self._intersects(line, text_box)
            and len(line.text.strip()) >= 2
            and line.text.strip() not in {"Send", "Search", "Q Search"}
        ]
        return "\n".join(lines).strip()

    def click_send(self, window: Any) -> bool:
        from pywinauto import mouse

        image = self._capture(window)
        send_box = self._send_button_box(image)
        abs_point = self._absolute_point(window, send_box.center)
        window.set_focus()
        time.sleep(0.05)
        mouse.click(coords=abs_point)
        return True

    def scroll_conversation_list(self, window: Any, *, wheel_dist: int) -> None:
        from pywinauto import mouse

        image = self._capture(window)
        list_box = self._conversation_list_box(image)
        anchor = (
            list_box.x1 + max(24, int(list_box.width * 0.35)),
            list_box.y1 + max(80, int(list_box.height * 0.35)),
        )
        abs_point = self._absolute_point(window, anchor)
        window.set_focus()
        time.sleep(0.05)
        mouse.scroll(coords=abs_point, wheel_dist=wheel_dist)

    def _capture(self, window: Any) -> np.ndarray:
        image = window.capture_as_image()
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def _conversation_list_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=int(w * 0.06), y1=int(h * 0.03), x2=int(w * 0.29), y2=int(h * 0.995))

    def _chat_nav_badge_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=0, y1=int(h * 0.04), x2=int(w * 0.07), y2=int(h * 0.18))

    def _chat_nav_click_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=0, y1=int(h * 0.07), x2=int(w * 0.065), y2=int(h * 0.17))

    def _chat_history_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=int(w * 0.30), y1=int(h * 0.08), x2=int(w * 0.98), y2=int(h * 0.77))

    def _input_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=int(w * 0.33), y1=int(h * 0.80), x2=int(w * 0.94), y2=int(h * 0.96))

    def _input_text_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=int(w * 0.34), y1=int(h * 0.80), x2=int(w * 0.90), y2=int(h * 0.90))

    def _send_button_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(x1=int(w * 0.90), y1=int(h * 0.935), x2=int(w * 0.97), y2=int(h * 0.985))

    def _group_chat_turns(self, chat_lines: list[OCRLine], chat_box: Box) -> list[ChatTurn]:
        turns: list[ChatTurn] = []
        current_direction: str | None = None
        current_lines: list[OCRLine] = []

        for line in chat_lines:
            direction = self._line_direction(line, chat_box)
            if direction is None:
                continue

            if current_lines and (
                direction != current_direction or line.y1 - current_lines[-1].y2 > max(36, int(chat_box.height * 0.06))
            ):
                turns.append(self._build_turn(current_direction or "unknown", current_lines))
                current_lines = []

            current_direction = direction
            current_lines.append(line)

        if current_lines:
            turns.append(self._build_turn(current_direction or "unknown", current_lines))
        return [turn for turn in turns if turn.text]

    def _build_turn(self, direction: str, lines: list[OCRLine]) -> ChatTurn:
        text = "\n".join(line.text.strip() for line in lines if line.text.strip())
        return ChatTurn(direction=direction, text=text.strip(), y1=int(lines[0].y1), y2=int(lines[-1].y2))

    def _line_direction(self, line: OCRLine, chat_box: Box) -> str | None:
        incoming_boundary = chat_box.x1 + chat_box.width * 0.44
        outgoing_boundary = chat_box.x1 + chat_box.width * 0.56
        if line.cx <= incoming_boundary:
            return "incoming"
        if line.cx >= outgoing_boundary:
            return "outgoing"
        return None

    def _find_red_badge_rows(self, image: np.ndarray, box: Box) -> list[int]:
        row_centers: list[int] = []
        for component in self._find_red_component_boxes(image, box, min_area=20):
            local_cx = component.center[0] - box.x1
            local_cy = component.center[1] - box.y1
            if local_cy < box.height * 0.075:
                continue
            if local_cx < box.width * 0.08:
                continue
            row_centers.append(component.center[1])
        return self._cluster_row_centers(row_centers, gap=max(32, int(box.height * 0.035)))

    def _cluster_row_centers(self, row_centers: list[int], *, gap: int) -> list[int]:
        if not row_centers:
            return []
        sorted_centers = sorted(row_centers)
        clusters: list[list[int]] = [[sorted_centers[0]]]
        for value in sorted_centers[1:]:
            if value - clusters[-1][-1] <= gap:
                clusters[-1].append(value)
            else:
                clusters.append([value])
        return [int(sum(cluster) / len(cluster)) for cluster in clusters]

    def _find_red_component_boxes(self, image: np.ndarray, box: Box, *, min_area: int) -> list[Box]:
        crop = image[box.y1 : box.y2, box.x1 : box.x2]
        if crop.size == 0:
            return []

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 90, 90]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 90, 90]), np.array([180, 255, 255]))
        mask = cv2.bitwise_or(mask1, mask2)
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask)

        components: list[Box] = []
        for label_index in range(1, num_labels):
            area = int(stats[label_index, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            left = int(stats[label_index, cv2.CC_STAT_LEFT])
            top = int(stats[label_index, cv2.CC_STAT_TOP])
            width = int(stats[label_index, cv2.CC_STAT_WIDTH])
            height = int(stats[label_index, cv2.CC_STAT_HEIGHT])
            components.append(Box(x1=box.x1 + left, y1=box.y1 + top, x2=box.x1 + left + width, y2=box.y1 + top + height))
        return components

    def _find_selected_row(self, image: np.ndarray, box: Box) -> int | None:
        crop = image[box.y1 : box.y2, box.x1 : box.x2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([40, 80, 60]), np.array([95, 255, 255]))
        num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(mask)

        best_label = None
        best_area = 0
        for label_index in range(1, num_labels):
            area = int(stats[label_index, cv2.CC_STAT_AREA])
            width = int(stats[label_index, cv2.CC_STAT_WIDTH])
            if area < 1500 or width < crop.shape[1] * 0.45:
                continue
            if area > best_area:
                best_area = area
                best_label = label_index

        if best_label is None:
            return None
        _, cy = centroids[best_label]
        return box.y1 + int(cy)

    def _contact_from_row(
        self,
        image: np.ndarray,
        ocr_lines: list[OCRLine],
        list_box: Box,
        row_center_y: int,
        *,
        unread_count: int,
    ) -> dict[str, Any]:
        row_half_height = max(32, int(image.shape[0] * 0.045))
        row_box = Box(
            x1=list_box.x1,
            y1=max(list_box.y1, row_center_y - row_half_height),
            x2=list_box.x2,
            y2=min(list_box.y2, row_center_y + row_half_height),
        )
        lines = [
            line
            for line in ocr_lines
            if self._intersects(line, row_box)
            and line.x1 <= row_box.x1 + row_box.width * 0.75
            and not self._is_time_like(line.text)
        ]
        lines.sort(key=lambda line: (line.cy, line.x1))
        contact_name = next((line.text for line in lines if len(line.text.strip()) >= 2), "current_chat")
        click_x = row_box.x1 + int(row_box.width * 0.35)
        return {
            "contact_name": contact_name,
            "unread_count": unread_count,
            "is_group_chat": "group" in contact_name.lower() or "群" in contact_name,
            "click_point": (click_x, row_center_y),
        }

    def _looks_like_contact_name(self, text: str) -> bool:
        raw = text.strip()
        if len(raw) < 2:
            return False
        if "search" in raw.lower():
            return False
        if self._is_time_like(raw):
            return False
        if any(marker in raw for marker in {",", ".", "?", "!", ":"}) and len(raw) > 12:
            return False
        return True

    def _extract_integer_from_box(self, ocr_lines: list[OCRLine], box: Box) -> int | None:
        for line in ocr_lines:
            if not self._intersects(line, box):
                continue
            digits = "".join(character for character in line.text if character.isdigit())
            if digits:
                return int(digits)
        return None

    def _is_time_like(self, text: str) -> bool:
        raw = text.strip()
        return bool(self.TIME_RE.match(raw) or self.DATE_HINT_RE.match(raw))

    def _intersects(self, line: OCRLine, box: Box) -> bool:
        return not (line.x2 < box.x1 or line.x1 > box.x2 or line.y2 < box.y1 or line.y1 > box.y2)

    def _absolute_point(self, window: Any, point: tuple[int, int]) -> tuple[int, int]:
        rect = window.rectangle()
        return (int(rect.left + point[0]), int(rect.top + point[1]))

    def _set_clipboard_text(self, text: str) -> None:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, str(text))
        finally:
            win32clipboard.CloseClipboard()
