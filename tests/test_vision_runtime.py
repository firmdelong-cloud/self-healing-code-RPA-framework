from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from message_runtime.conversation_logger import ConversationLogger
from message_runtime.reply_engine import ReplyEngine
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

    cv2.circle(image, (28, 110), 15, (0, 0, 255), thickness=-1)

    list_x1, list_x2 = 60, 290
    cv2.rectangle(image, (list_x1, 27), (list_x2, 895), (70, 70, 70), thickness=-1)
    cv2.rectangle(image, (list_x1, 500), (list_x2, 560), (50, 180, 90), thickness=-1)
    cv2.circle(image, (250, 150), 10, (0, 0, 255), thickness=-1)
    cv2.circle(image, (250, 270), 10, (0, 0, 255), thickness=-1)

    ocr_lines = [
        make_line("16", 14, 100, 38, 120),
        make_line("Contact A", 120, 132, 185, 148),
        make_line("12:02", 250, 132, 288, 148),
        make_line("Contact C", 120, 252, 185, 270),
        make_line("12:08", 250, 252, 288, 270),
        make_line("Contact B", 120, 520, 185, 538),
        make_line("12:11", 250, 520, 288, 538),
        make_line("hello", 350, 120, 390, 140),
        make_line("price question", 340, 420, 445, 442),
        make_line("ok", 720, 520, 750, 542),
    ]
    return FakeWindow(image), ocr_lines


def make_last_incoming_window() -> tuple[FakeWindow, list[OCRLine]]:
    window, lines = make_synthetic_wechat_window()
    lines.append(make_line("please send quote", 340, 600, 470, 624))
    return window, lines


def test_vision_detects_unread_contact_row():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    result = vision.find_unread_contact(window)

    assert result is not None
    assert result["contact_name"] == "Contact A"
    assert result["unread_count"] == 1
    assert result["click_point"][1] >= 140


def test_vision_detects_visible_unread_queue():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    results = vision.find_unread_contacts(window)

    assert [result["contact_name"] for result in results] == ["Contact A", "Contact C"]


def test_vision_detects_unread_collection_badge():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    result = vision.read_unread_collection(window)

    assert result is not None
    assert result["has_unread"] is True
    assert result["count"] == 16


def test_vision_detects_active_contact_row():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    result = vision.find_active_contact(window)

    assert result is not None
    assert result["contact_name"] == "Contact B"
    assert result["unread_count"] == 0


def test_vision_reads_chat_turns_with_directions():
    window, lines = make_synthetic_wechat_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    turns = vision.read_chat_turns(window, limit=10)

    assert [turn.direction for turn in turns] == ["incoming", "incoming", "outgoing"]
    assert turns[-1].text == "ok"


def test_vision_reads_latest_incoming_message():
    window, lines = make_last_incoming_window()
    vision = WeChatVision(ocr_reader=FakeOcrReader(lines))

    latest = vision.read_latest_incoming_message(window)

    assert latest == "please send quote"


def test_conversation_logger_detects_recently_handled_message(tmp_path):
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat")
    logger.record("message_sent", contact_name="Contact A", payload={"latest_message": "please send quote", "reply_text": "ok"})

    assert logger.was_recent_message_handled("Contact A", "please send quote") is True
    assert logger.was_recent_message_handled("Contact A", "new request") is False


def test_reply_engine_uses_history_context():
    engine = ReplyEngine()
    reply = engine.generate(
        intent="general_inquiry",
        latest_message="wait a moment",
        contact_name="Contact A",
        recent_history=[
            {"direction": "outgoing", "text": "I will send quotation ideas first"},
            {"direction": "incoming", "text": "wait a moment"},
        ],
    )

    assert "keep following" in reply.reply_text
