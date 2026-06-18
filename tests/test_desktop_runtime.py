from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from desktop_runtime.desktop_step_runner import DesktopMessageExecutor, DesktopStepRunner
from desktop_runtime.input_controller import fill_text, send_message
from message_runtime.auto_send_policy import AutoSendPolicy
from message_runtime.conversation_logger import ConversationLogger
from message_runtime.intent_classifier import IntentClassifier
from message_runtime.reply_engine import ReplyEngine
from message_runtime.safety_guard import SafetyDecision, SafetyGuard

from example_skills.wechat_auto_reply_mock.main import run as run_wechat_skill


class FakeDesktopWindow:
    def __init__(self, *, latest_message: str = "hello, how much is it?", is_group_chat: bool = False):
        self.latest_message = latest_message
        self.is_group_chat = is_group_chat
        self.contact_name = "Customer A" if not is_group_chat else "Sales Group"
        self.url = "desktop://wechat-mock"
        self.opened_url: str | None = None
        self.draft_text = ""
        self.sent_messages: list[str] = []

    def open(self, url: str) -> None:
        self.opened_url = url
        self.url = url

    def detect_unread(self, selector: str) -> dict[str, object]:
        return {
            "contact_name": self.contact_name,
            "unread_count": 1,
            "is_group_chat": self.is_group_chat,
        }

    def click_chat(self, selector: str) -> dict[str, object]:
        return {
            "contact_name": self.contact_name,
            "is_group_chat": self.is_group_chat,
        }

    def read_chat_text(self, selector: str) -> str:
        return self.latest_message

    def fill_text(self, selector: str, value: str) -> None:
        self.draft_text = value

    def send_message(self, selector: str) -> bool:
        self.sent_messages.append(self.draft_text)
        return True

    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"desktop screenshot")

    def content(self) -> str:
        return f"<html><body>{self.latest_message}</body></html>"

    def state(self) -> dict[str, object]:
        return {
            "contact_name": self.contact_name,
            "latest_message": self.latest_message,
            "draft_text": self.draft_text,
            "is_group_chat": self.is_group_chat,
        }


def make_skill(*, auto_send: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id="wechat_auto_reply_mock",
        name="WeChat Auto Reply Mock",
        version="0.1.0",
        runtime="desktop_mock",
        raw={"desktop": {}},
        selectors={
            "unread_chat_item": {"primary": ".contact-item.unread", "fallbacks": []},
            "latest_incoming_message": {"primary": ".message.incoming", "fallbacks": []},
            "reply_input": {"primary": "#reply-box", "fallbacks": []},
            "send_button": {"primary": "#send-button", "fallbacks": []},
        },
        policy={
            "mode": "controlled_auto_reply",
            "auto_send": auto_send,
            "allow_group_chat": False,
            "max_replies_per_contact_per_hour": 3,
            "max_total_replies_per_hour": 20,
            "blocked_intents": [
                "refund_dispute",
                "legal_issue",
                "payment_sensitive",
                "complaint",
            ],
            "fallback_to_human": True,
        },
        steps=[],
    )


def make_runner(tmp_path: Path, *, auto_send: bool = True) -> DesktopStepRunner:
    return DesktopStepRunner(skill=make_skill(auto_send=auto_send), storage_root=tmp_path)


def test_detect_unread_chat(tmp_path: Path) -> None:
    outputs: dict[str, object] = {}
    result = make_runner(tmp_path).run(
        FakeDesktopWindow(),
        {"id": "detect", "type": "detect_unread", "goal": "Detect", "selector_ref": "unread_chat_item"},
        outputs=outputs,
    )

    assert result.status == "success"
    assert outputs["contact_name"] == "Customer A"
    assert outputs["unread_count"] == 1


def test_open_unread_chat(tmp_path: Path) -> None:
    outputs = {"contact_name": "Customer A", "is_group_chat": False}
    result = make_runner(tmp_path).run(
        FakeDesktopWindow(),
        {"id": "open", "type": "click_chat", "goal": "Open chat", "selector_ref": "unread_chat_item"},
        outputs=outputs,
    )

    assert result.status == "success"
    assert outputs["contact_name"] == "Customer A"


def test_read_recent_message(tmp_path: Path) -> None:
    outputs = {"contact_name": "Customer A", "is_group_chat": False}
    result = make_runner(tmp_path).run(
        FakeDesktopWindow(latest_message="hello, how much is it?"),
        {"id": "read", "type": "read_chat_text", "goal": "Read", "selector_ref": "latest_incoming_message"},
        outputs=outputs,
    )

    assert result.status == "success"
    assert outputs["latest_message"] == "hello, how much is it?"
    assert outputs["normalized_text"] == "hello, how much is it?"


def test_classify_price_inquiry() -> None:
    result = IntentClassifier().classify("hello, how much is it?")

    assert result.intent == "price_inquiry"
    assert result.risk_level == "low"


def test_generate_reply() -> None:
    reply = ReplyEngine().generate(
        intent="price_inquiry",
        latest_message="hello, how much is it?",
        contact_name="Customer A",
    )

    assert "quotation reference" in reply.reply_text


def test_safety_guard_blocks_refund_dispute() -> None:
    guard = SafetyGuard()
    decision = guard.evaluate(
        intent="refund_dispute",
        latest_message="I want a refund",
        policy=make_skill().policy,
    )

    assert decision.allowed is False
    assert decision.handoff_required is True


def test_auto_send_policy_allows_low_risk_message(tmp_path: Path) -> None:
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat_auto_reply_mock")
    decision = AutoSendPolicy().evaluate(
        contact_name="Customer A",
        is_group_chat=False,
        policy=make_skill().policy,
        logger=logger,
        safety_decision=SafetyDecision(allowed=True, handoff_required=False, reasons=[], risk_level="low"),
    )

    assert decision.allowed is True
    assert decision.handoff_required is False


def test_auto_send_policy_blocks_group_chat(tmp_path: Path) -> None:
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat_auto_reply_mock")
    decision = AutoSendPolicy().evaluate(
        contact_name="Sales Group",
        is_group_chat=True,
        policy=make_skill().policy,
        logger=logger,
        safety_decision=SafetyDecision(allowed=True, handoff_required=False, reasons=[], risk_level="low"),
    )

    assert decision.allowed is False
    assert "group_chat_blocked" in decision.reasons


def test_auto_send_policy_blocks_over_limit(tmp_path: Path) -> None:
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat_auto_reply_mock")
    for index in range(3):
        logger.record("message_sent", contact_name="Customer A", payload={"index": index})

    decision = AutoSendPolicy().evaluate(
        contact_name="Customer A",
        is_group_chat=False,
        policy=make_skill().policy,
        logger=logger,
        safety_decision=SafetyDecision(allowed=True, handoff_required=False, reasons=[], risk_level="low"),
    )

    assert decision.allowed is False
    assert "contact_hourly_limit_reached" in decision.reasons


def test_fill_reply_box() -> None:
    window = FakeDesktopWindow()
    fill_text(window, "#reply-box", "Hello, I can share a quotation reference.")

    assert window.draft_text == "Hello, I can share a quotation reference."


def test_send_reply() -> None:
    window = FakeDesktopWindow()
    window.draft_text = "Hello, I can share a quotation reference."

    sent = send_message(window, "#send-button")

    assert sent is True
    assert window.sent_messages == ["Hello, I can share a quotation reference."]


def test_conversation_logger_records_sent_message(tmp_path: Path) -> None:
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat_auto_reply_mock")
    logger.record("message_sent", contact_name="Customer A", payload={"reply_text": "ok"})

    events = (tmp_path / "conversations" / "wechat_auto_reply_mock.jsonl").read_text(encoding="utf-8")
    assert "message_sent" in events
    assert logger.count_sent_for_contact("Customer A", within_hours=1) == 1


def test_conversation_logger_detects_recent_reply_echo(tmp_path: Path) -> None:
    logger = ConversationLogger(tmp_path / "conversations", skill_id="wechat_auto_reply_mock")
    reply_text = "Hello, I have received your message. Please tell me what you need."
    logger.record("draft_filled", contact_name="Customer A", payload={"reply_text": reply_text})

    assert logger.looks_like_recent_reply_echo("Customer A", reply_text) is True
    assert logger.looks_like_recent_reply_echo("Customer A", reply_text + ".") is True
    assert logger.looks_like_recent_reply_echo("Customer A", "new quote request") is False


@pytest.mark.integration
def test_wechat_auto_reply_mock_skill(tmp_path: Path) -> None:
    result = run_wechat_skill(storage_root=tmp_path, scenario="price")

    assert result.status == "success"
    assert result.outputs["contact_name"] == "Customer A"
    assert result.outputs["latest_message"] == "hello, how much is it?"
    assert result.outputs["intent"] == "price_inquiry"
    assert result.outputs["auto_send_allowed"] is True
    assert result.outputs["sent"] is True
    assert result.outputs["handoff_required"] is False


@pytest.mark.integration
def test_wechat_auto_reply_mock_high_risk_handoff(tmp_path: Path) -> None:
    result = run_wechat_skill(storage_root=tmp_path, scenario="refund")

    assert result.status == "success"
    assert result.outputs["intent"] == "refund_dispute"
    assert result.outputs["sent"] is False
    assert result.outputs["handoff_required"] is True


def test_cli_desktop_simulate(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "code_rpa",
            "--project-root",
            str(Path(__file__).resolve().parents[1]),
            "desktop",
            "simulate",
            "wechat_auto_reply_mock",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "success"
    assert payload["sent"] is True
    assert payload["auto_send_allowed"] is True


def test_desktop_executor_captures_failure_snapshot(tmp_path: Path) -> None:
    skill = make_skill()
    skill.steps = [
        {"id": "open", "type": "open_window", "goal": "Open", "url": "file:///wechat_mock.html"},
        {"id": "unknown", "type": "unknown_step", "goal": "Fail"},
    ]
    window = FakeDesktopWindow()
    executor = DesktopMessageExecutor(storage_root=tmp_path)
    result = executor.run(skill, page=window)

    assert result.status == "failed"
    assert result.failure_snapshot is not None
    assert Path(result.failure_snapshot.state_path).exists()
