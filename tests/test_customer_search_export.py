from pathlib import Path
import importlib.util

import pytest

from skill_registry.loader import SkillLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / "example_skills" / "customer_search_export"
spec = importlib.util.spec_from_file_location("customer_search_export_main", SKILL_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run = module.run


def test_customer_search_export_skill_loads():
    skill = SkillLoader().load(SKILL_DIR / "skill.yaml")

    assert skill.id == "customer_search_export"
    assert skill.version == "0.1.0"
    assert len(skill.steps) == 6


@pytest.mark.integration
def test_customer_search_export_skill(tmp_path):
    result = run(storage_root=tmp_path)

    assert result.status == "success"
    assert result.outputs["table_rows"] == 2
    assert Path(result.outputs["csv_path"]).exists()
    assert "Acme Logistics" in Path(result.outputs["csv_path"]).read_text(encoding="utf-8")
