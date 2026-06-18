from pathlib import Path

from skill_registry.loader import SkillLoader
from skill_registry.validator import SkillValidator


def test_skill_loads() -> None:
    skill = SkillLoader().load(Path(__file__).resolve().parents[1] / "skill.yaml")

    assert skill.id == "report_export_and_summary"
    assert skill.nodes
    assert skill.nodes[-1]["component"] == "system.log"


def test_skill_validates() -> None:
    project_root = Path(__file__).resolve().parents[3]
    result = SkillValidator(project_root).validate("report_export_and_summary")

    assert result.status == "ok"
