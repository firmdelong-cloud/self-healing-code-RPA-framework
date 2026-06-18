from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from vision_runtime.ocr_reader import OCRLine
from vision_runtime.wechat_vision import WeChatVision


class FakeOcrReader:
    def __init__(self, lines: list[OCRLine]):
        self.lines = lines

    def read(self, image):  # noqa: ANN001
        return list(self.lines)


@dataclass
class FakeRect:
    left: int = 10
    top: int = 20
    right: int = 1010
    bottom: int = 920


class FakeWindow:
    def __init__(self, image: np.ndarray):
        self._image = image

    def capture_as_image(self):
        rgb = cv2.cvtColor(self._image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def rectangle(self):
        return FakeRect()


def make_line(text: str, x1: float, y1: float, x2: float, y2: float) -> OCRLine:
    return OCRLine(
        text=text,
        score=0.99,
        points=((x1, y1), (x2, y1), (x2, y2), (x1, y2)),
    )


def make_synthetic_wechat_window() -> tuple[FakeWindow, list[OCRLine]]:
    image = np.zeros((900, 1000, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)

    list_x1, list_x2 = 60, 290
    cv2.rectangle(image, (list_x1, 27), (list_x2, 895), (70, 70, 70), thickness=-1)

    # Selected active row.
    cv2.rectangle(image, (list_x1, 500), (list_x2, 560), (50, 180, 90), thickness=-1)

    # Unread contact red badge.
    cv2.circle(image, (250, 150), 10, (0, 0, 255), thickness=-1)

    ocr_lines = [
        make_line("客户A", 120, 132, 170, 148),
        make_line("12:02", 250, 132, 288, 148),
        make_line("客户B", 120, 520, 170, 538),
        make_line("昨天", 250, 520, 285, 538),
        make_line("你好", 350, 120, 390, 140),
        make_line("12:02", 570, 250, 610, 270),
        make_line("价格多少", 340, 420, 430, 442),
        make_line("可以", 720, 520, 770, 542),
    ]
    return FakeWindow(image), ocr_lines


def test_vision_detects_unread_contact_row():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    result = vision.find_unread_contact(window)

    assert result is not None
    assert result["contact_name"] == "客户A"
    assert result["unread_count"] == 1
    assert result["click_point"][1] >= 140


def test_vision_detects_active_contact_row():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    result = vision.find_active_contact(window)

    assert result is not None
    assert result["contact_name"] == "客户B"
    assert result["unread_count"] == 0


def test_vision_reads_latest_incoming_message():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    latest = vision.read_latest_incoming_message(window)

    assert latest == "价格多少"
