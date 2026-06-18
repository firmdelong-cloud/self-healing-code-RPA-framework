from __future__ import annotations

from pathlib import Path

from event_runtime import Event, EventLoop, EventMemoryStore
from procedure_runtime import ProcedureExecutor
from rpa_runtime.executor import RPAExecutor
from skill_core import EventSkillDefinition, SkillKind
from skill_registry.loader import SkillLoader
from skill_registry.validator import SkillValidator


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeDetector:
    def detect(self) -> list[Event]:
        return [
            Event(
                event_id="evt-1",
                event_type="unread_message",
                subject_id="contact-a",
                source="wechat",
                payload={"latest_message": "hello"},
            )
        ]


class FakeContextBuilder:
    def build(self, event: Event) -> dict[str, object]:
        return {
            "latest_turn": {"direction": "incoming", "text": event.payload["latest_message"]},
            "is_group_chat": False,
        }


def test_loader_marks_existing_skills_as_procedure_skill() -> None:
    skill = SkillLoader().load(PROJECT_ROOT / "example_skills" / "web_report_export" / "skill.yaml")

    assert skill.skill_type == SkillKind.PROCEDURE


def test_procedure_runtime_alias_uses_existing_executor() -> None:
    assert ProcedureExecutor is RPAExecutor


def test_event_skill_schema_loads_experimental_wechat_skill() -> None:
    skill = EventSkillDefinition.load(
        PROJECT_ROOT / "experimental" / "event_skills" / "wechat_auto_reply" / "event_skill.yaml"
    )

    assert skill.id == "wechat_auto_reply"
    assert skill.raw["type"] == "event_skill"
    assert skill.reply_policy["mode"] == "draft_only"
    assert skill.reply_policy["auto_send"] is False


def test_event_loop_processes_event_as_draft(tmp_path: Path) -> None:
    loop = EventLoop(
        detector=FakeDetector(),
        context_builder=FakeContextBuilder(),
        memory_store=EventMemoryStore(tmp_path / "memory"),
    )

    result = loop.poll(
        decision_policy={"allow_group_chat": False, "draft_only": True},
        reply_policy={"draft_only": True, "require_human_confirm": True},
    )

    assert result.status == "ok"
    assert result.processed == 1
    assert result.actions[0]["action"]["action_mode"] == "confirm"


def test_event_loop_skips_already_handled_event(tmp_path: Path) -> None:
    memory = EventMemoryStore(tmp_path / "memory")
    memory.mark_handled("evt-1", {"reason": "previous_run"})
    loop = EventLoop(
        detector=FakeDetector(),
        context_builder=FakeContextBuilder(),
        memory_store=memory,
    )

    result = loop.poll(
        decision_policy={"allow_group_chat": False, "draft_only": True},
        reply_policy={"draft_only": True},
    )

    assert result.actions[0]["decision"]["should_act"] is False
    assert result.actions[0]["action"]["action_mode"] == "skip"


def test_skill_validator_accepts_procedure_skill_type() -> None:
    result = SkillValidator(PROJECT_ROOT).validate("web_report_export")

    assert result.status == "ok"
