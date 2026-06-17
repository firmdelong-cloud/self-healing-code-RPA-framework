from pathlib import Path
import json
import shutil

import yaml

from code_rpa.cli import main
from skill_registry.validator import SkillValidator


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_project(tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target


def test_skill_validate_success():
    validator = SkillValidator(PROJECT_ROOT)

    web_result = validator.validate("web_report_export")
    customer_result = validator.validate("customer_search_export")

    assert web_result.status == "ok"
    assert web_result.errors == []
    assert customer_result.status == "ok"
    assert customer_result.errors == []


def test_skill_validate_missing_skill_yaml(tmp_path):
    project = copy_project(tmp_path)
    (project / "example_skills" / "customer_search_export" / "skill.yaml").unlink()

    result = SkillValidator(project).validate("customer_search_export")

    assert result.status == "error"
    assert any("skill.yaml" in error for error in result.errors)


def test_skill_validate_missing_selector(tmp_path):
    project = copy_project(tmp_path)
    selectors_path = project / "example_skills" / "customer_search_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8"))
    selectors.pop("customer_results_table")
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")

    result = SkillValidator(project).validate("customer_search_export")

    assert result.status == "error"
    assert any("references missing selector 'customer_results_table'" in error for error in result.errors)


def test_skill_validate_missing_repair_policy(tmp_path):
    project = copy_project(tmp_path)
    (project / "example_skills" / "customer_search_export" / "repair_policy.yaml").unlink()

    result = SkillValidator(project).validate("customer_search_export")

    assert result.status == "error"
    assert any("repair_policy.yaml" in error for error in result.errors)


def test_skill_validate_rejects_code_changes_default(tmp_path):
    project = copy_project(tmp_path)
    repair_policy_path = project / "example_skills" / "customer_search_export" / "repair_policy.yaml"
    policy = yaml.safe_load(repair_policy_path.read_text(encoding="utf-8"))
    policy["repair_scope"]["scope_type"] = "code_changes"
    repair_policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    result = SkillValidator(project).validate("customer_search_export")

    assert result.status == "error"
    assert any("code_changes" in error for error in result.errors)


def test_skill_validate_warns_missing_fallbacks(tmp_path):
    project = copy_project(tmp_path)
    selectors_path = project / "example_skills" / "customer_search_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8"))
    selectors["customer_keyword_input"].pop("fallbacks")
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")

    result = SkillValidator(project).validate("customer_search_export")

    assert result.status == "ok"
    assert any("has no fallback selectors" in warning for warning in result.warnings)


def test_cli_skill_validate(capsys):
    exit_code = main(["--project-root", str(PROJECT_ROOT), "skill", "validate", "customer_search_export"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["skill_id"] == "customer_search_export"


def test_codex_generate_skill_doc_exists():
    doc = PROJECT_ROOT / "docs" / "codex-generate-skill.md"

    assert doc.exists()
    content = doc.read_text(encoding="utf-8")
    assert "customer_search_export" in content
    assert "Do not modify runtime code" in content
    assert "python -m code_rpa skill validate" in content


def test_repo_skill_instructions_include_quality_gate():
    skill_doc = PROJECT_ROOT / ".agents" / "skills" / "self-healing-rpa-engineer" / "SKILL.md"
    content = skill_doc.read_text(encoding="utf-8")

    assert "python -m code_rpa skill validate <skill_id>" in content
    assert "python -m code_rpa skill test <skill_id>" in content
    assert "python -m pytest" in content
    assert "tests/fixtures/" in content
    assert "selector_resolver" in content
