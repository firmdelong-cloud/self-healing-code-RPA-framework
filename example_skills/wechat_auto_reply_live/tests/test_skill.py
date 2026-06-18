from pathlib import Path

from skill_registry.loader import SkillLoader
from skill_registry.validator import SkillValidator


def test_skill_loads() -> None:
    skill = SkillLoader().load(Path(__file__).resolve().parents[1] / "skill.yaml")
    assert skill.id == "wechat_auto_reply_live"
    assert skill.runtime == "desktop_wechat"
    assert skill.policy["auto_send"] is False
    assert skill.raw["desktop"]["window_title_regex"] == "WeChat|微信"


def test_skill_validates_for_live_desktop() -> None:
    project_root = Path(__file__).resolve().parents[3]
    result = SkillValidator(project_root).validate("wechat_auto_reply_live")
    assert result.status == "ok"
