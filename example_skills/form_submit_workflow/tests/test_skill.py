from pathlib import Path
import importlib.util

import pytest

from skill_registry.loader import SkillLoader


SKILL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("form_submit_workflow_main", SKILL_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run = module.run


def test_skill_loads():
    skill = SkillLoader().load(SKILL_DIR / "skill.yaml")

    assert skill.id == "form_submit_workflow"
    assert skill.version == "0.1.0"
    assert len(skill.steps) == 6


@pytest.mark.integration
def test_form_submit_workflow_skill(tmp_path):
    result = run(storage_root=tmp_path)

    assert result.status == "success"
    assert result.steps[-1].step_id == "verify_submit_success"
    assert result.steps[-1].status == "success"
