"""Vision fallback for real WeChat desktop windows."""

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


class WeChatVision:
    """Best-effort visual analysis for Qt-based WeChat desktop windows."""

    TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
    DATE_HINT_RE = re.compile(r"^(昨天|今天|星期|周|[0-9]{2}/[0-9]{2})")

    def __init__(self, ocr_reader: Any | None = None) -> None:
        self.ocr_reader = ocr_reader or RapidOcrReader()

    def find_unread_contact(self, window: Any) -> dict[str, Any] | None:
        image = self._capture(window)
        list_box = self._conversation_list_box(image)
        unread_rows = self._find_red_badge_rows(image, list_box)
        ocr_lines = self.ocr_reader.read(image)
        for row_y in unread_rows:
            contact = self._contact_from_row(image, ocr_lines, list_box, row_y, unread_count=1)
            if self._looks_like_contact_name(contact["contact_name"]):
                return contact
        return None

    def find_active_contact(self, window: Any) -> dict[str, Any] | None:
        image = self._capture(window)
        list_box = self._conversation_list_box(image)
        active_row = self._find_selected_row(image, list_box)
        if active_row is None:
            return None
        ocr_lines = self.ocr_reader.read(image)
        return self._contact_from_row(image, ocr_lines, list_box, active_row, unread_count=0)

    def read_latest_incoming_message(self, window: Any) -> str:
        image = self._capture(window)
        chat_box = self._chat_history_box(image)
        ocr_lines = self.ocr_reader.read(image)
        chat_lines = [line for line in ocr_lines if self._intersects(line, chat_box) and not self._is_time_like(line.text)]
        if not chat_lines:
            raise RuntimeError("no OCR text found in the current chat history")

        incoming_lines = [line for line in chat_lines if line.cx <= chat_box.x1 + chat_box.width * 0.42]
        target_pool = incoming_lines or chat_lines
        target = max(target_pool, key=lambda line: (line.cy, -line.cx))
        return target.text

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

    def click_send(self, window: Any) -> bool:
        from pywinauto import mouse

        image = self._capture(window)
        send_box = self._send_button_box(image)
        abs_point = self._absolute_point(window, send_box.center)
        window.set_focus()
        time.sleep(0.05)
        mouse.click(coords=abs_point)
        return True

    def _capture(self, window: Any) -> np.ndarray:
        image = window.capture_as_image()
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def _conversation_list_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(
            x1=int(w * 0.06),
            y1=int(h * 0.03),
            x2=int(w * 0.29),
            y2=int(h * 0.995),
        )

    def _chat_history_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(
            x1=int(w * 0.30),
            y1=int(h * 0.08),
            x2=int(w * 0.98),
            y2=int(h * 0.77),
        )

    def _input_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(
            x1=int(w * 0.33),
            y1=int(h * 0.80),
            x2=int(w * 0.94),
            y2=int(h * 0.96),
        )

    def _send_button_box(self, image: np.ndarray) -> Box:
        h, w = image.shape[:2]
        return Box(
            x1=int(w * 0.90),
            y1=int(h * 0.935),
            x2=int(w * 0.97),
            y2=int(h * 0.985),
        )

    def _find_red_badge_rows(self, image: np.ndarray, box: Box) -> list[int]:
        crop = image[box.y1:box.y2, box.x1:box.x2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 90, 90]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 90, 90]), np.array([180, 255, 255]))
        mask = cv2.bitwise_or(mask1, mask2)
        num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(mask)

        row_centers: list[int] = []
        for label_index in range(1, num_labels):
            area = int(stats[label_index, cv2.CC_STAT_AREA])
            if area < 20:
                continue
            cx, cy = centroids[label_index]
            if cy < crop.shape[0] * 0.075:
                continue
            if cx < crop.shape[1] * 0.55:
                continue
            row_centers.append(box.y1 + int(cy))
        return sorted(set(row_centers))

    def _find_selected_row(self, image: np.ndarray, box: Box) -> int | None:
        crop = image[box.y1:box.y2, box.x1:box.x2]
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
        contact_name = next((line.text for line in lines if len(line.text) >= 2), "当前聊天")
        click_x = row_box.x1 + int(row_box.width * 0.35)
        return {
            "contact_name": contact_name,
            "unread_count": unread_count,
            "is_group_chat": "群" in contact_name,
            "click_point": (click_x, row_center_y),
        }

    def _looks_like_contact_name(self, text: str) -> bool:
        raw = text.strip()
        if len(raw) < 2:
            return False
        if "搜索" in raw:
            return False
        if self._is_time_like(raw):
            return False
        return True

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
