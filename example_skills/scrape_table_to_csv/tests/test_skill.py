from pathlib import Path
import importlib.util

import pytest

from skill_registry.loader import SkillLoader


SKILL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scrape_table_to_csv_main", SKILL_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run = module.run


def test_skill_loads():
    skill = SkillLoader().load(SKILL_DIR / "skill.yaml")

    assert skill.id == "scrape_table_to_csv"
    assert skill.version == "0.1.0"
    assert len(skill.steps) == 4


@pytest.mark.integration
def test_scrape_table_to_csv_skill(tmp_path):
    result = run(storage_root=tmp_path)

    assert result.status == "success"
    assert result.outputs["table_rows"] == 3
    assert Path(result.outputs["csv_path"]).exists()
    assert "R-1001" in Path(result.outputs["csv_path"]).read_text(encoding="utf-8")
