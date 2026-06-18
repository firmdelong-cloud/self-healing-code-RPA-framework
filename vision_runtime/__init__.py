"""Vision-based desktop helpers for Qt-style chat windows."""

from .ocr_reader import OCRLine, RapidOcrReader
from .wechat_vision import ChatTurn, WeChatVision

__all__ = ["OCRLine", "RapidOcrReader", "ChatTurn", "WeChatVision"]
