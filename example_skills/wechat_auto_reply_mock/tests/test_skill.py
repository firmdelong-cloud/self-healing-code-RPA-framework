from pathlib import Path

from skill_registry.loader import SkillLoader


def test_skill_loads() -> None:
    skill = SkillLoader().load(Path(__file__).resolve().parents[1] / "skill.yaml")
    assert skill.id == "wechat_auto_reply_mock"
    assert skill.runtime == "desktop_mock"
    assert skill.policy["mode"] == "controlled_auto_reply"


def test_fixture_exists() -> None:
    fixture_path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "wechat_mock.html"
    assert fixture_path.exists()
