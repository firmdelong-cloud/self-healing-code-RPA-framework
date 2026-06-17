import json
from pathlib import Path
import shutil

import yaml

from code_rpa.cli import (
    DemoCustomerPage,
    apply_repair_patch,
    build_codex_customer_patch,
    degrade_customer_keyword_selector,
    main,
    prepare_customer_skill,
)
from repair_agent.patch_validator import PatchValidator
from rpa_runtime.executor import RPAExecutor
from skill_registry.loader import SkillLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_project(tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target


def prepare_failure(project_root: Path):
    degrade_customer_keyword_selector(project_root)
    skill_path = project_root / "example_skills" / "customer_search_export" / "skill.yaml"
    skill = prepare_customer_skill(project_root, SkillLoader().load(skill_path))
    result = RPAExecutor(storage_root=project_root / "storage").run(skill, page=DemoCustomerPage())
    repair_request_path = Path(result.repair_request_path)
    repair_request = json.loads(repair_request_path.read_text(encoding="utf-8"))
    return skill, result, repair_request_path, repair_request


def write_patch(path: Path, patch: dict) -> Path:
    path.write_text(json.dumps(patch, indent=2), encoding="utf-8")
    return path


def customer_primary(project_root: Path) -> str:
    selectors_path = project_root / "example_skills" / "customer_search_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    return selectors["customer_keyword_input"]["primary"]


def test_patch_format_doc_exists():
    doc = PROJECT_ROOT / "docs" / "patch-format.md"

    assert doc.exists()
    content = doc.read_text(encoding="utf-8")
    assert "repair_request_id" in content
    assert "selector_only" in content
    assert "changes" in content


def test_patch_validator_accepts_selector_only_patch(tmp_path):
    project = copy_project(tmp_path)
    skill, _, _, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)

    result = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert result.is_valid is True
    assert result.to_dict() == {
        "allowed": True,
        "reasons": [],
        "changed_files": ["example_skills/customer_search_export/selectors.yaml"],
        "patch_scope": "selector_only",
    }


def test_patch_validator_rejects_wrong_skill_id(tmp_path):
    project = copy_project(tmp_path)
    skill, _, _, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["skill_id"] = "other_skill"

    result = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert result.is_valid is False
    assert any("skill_id" in reason for reason in result.reasons)


def test_patch_validator_rejects_wrong_failed_step_id(tmp_path):
    project = copy_project(tmp_path)
    skill, _, _, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["failed_step_id"] = "click_search"

    result = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert result.is_valid is False
    assert any("failed_step_id" in reason for reason in result.reasons)


def test_patch_validator_rejects_python_file_change(tmp_path):
    project = copy_project(tmp_path)
    skill, _, _, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["changes"][0]["file"] = "example_skills/customer_search_export/main.py"

    result = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert result.is_valid is False
    assert any("protected" in reason or "selectors.yaml" in reason for reason in result.reasons)


def test_patch_validator_rejects_unrelated_selector(tmp_path):
    project = copy_project(tmp_path)
    skill, _, _, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["changes"][0]["selector_id"] = "customer_results_table"

    result = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert result.is_valid is False
    assert any("selector_id" in reason for reason in result.reasons)


def test_repair_apply_validates_before_apply(tmp_path):
    project = copy_project(tmp_path)
    _, _, repair_request_path, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["skill_id"] = "wrong_skill"
    patch_path = write_patch(tmp_path / "bad_patch.json", patch)

    result = apply_repair_patch(
        project_root=project,
        repair_request_path=repair_request_path,
        patch_path=patch_path,
    )

    assert result["validated"] is False
    assert result["sandbox_success"] is False
    assert customer_primary(project) == "#missing-customer-keyword"


def test_repair_apply_does_not_apply_on_invalid_patch(tmp_path):
    project = copy_project(tmp_path)
    _, _, repair_request_path, repair_request = prepare_failure(project)
    patch = build_codex_customer_patch(repair_request)
    patch["changes"][0]["selector_id"] = "customer_results_table"
    patch_path = write_patch(tmp_path / "bad_patch.json", patch)

    result = apply_repair_patch(
        project_root=project,
        repair_request_path=repair_request_path,
        patch_path=patch_path,
    )

    assert result["success"] is False
    assert customer_primary(project) == "#missing-customer-keyword"
    assert not (project / "storage" / "versions" / "customer_search_export").exists()


def test_repair_apply_creates_version_snapshot(tmp_path):
    project = copy_project(tmp_path)
    _, _, repair_request_path, repair_request = prepare_failure(project)
    patch_path = write_patch(tmp_path / "patch.json", build_codex_customer_patch(repair_request))

    result = apply_repair_patch(
        project_root=project,
        repair_request_path=repair_request_path,
        patch_path=patch_path,
    )
    versions = list((project / "storage" / "versions" / "customer_search_export").iterdir())

    assert result["success"] is True
    assert result["version_id"]
    assert len([path for path in versions if path.is_dir()]) >= 2
    assert customer_primary(project) == "#customer-keyword"


def test_repair_apply_reruns_skill_success(tmp_path):
    project = copy_project(tmp_path)
    _, _, repair_request_path, repair_request = prepare_failure(project)
    patch_path = write_patch(tmp_path / "patch.json", build_codex_customer_patch(repair_request))

    result = apply_repair_patch(
        project_root=project,
        repair_request_path=repair_request_path,
        patch_path=patch_path,
    )

    assert result["success"] is True
    assert result["rerun_status"] == "success"


def test_cli_repair_apply(tmp_path, capsys):
    project = copy_project(tmp_path)
    _, _, repair_request_path, repair_request = prepare_failure(project)
    patch_path = write_patch(tmp_path / "patch.json", build_codex_customer_patch(repair_request))

    exit_code = main([
        "--project-root",
        str(project),
        "repair",
        "apply",
        str(repair_request_path),
        str(patch_path),
    ])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["success"] is True
    assert payload["validated"] is True
    assert payload["sandbox_success"] is True
    assert payload["rerun_status"] == "success"


def test_cli_demo_codex_patch(capsys):
    exit_code = main(["--project-root", str(PROJECT_ROOT), "demo", "codex-patch"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["success"] is True
    assert payload["validated"] is True
    assert payload["sandbox_success"] is True
    assert payload["rerun_status"] == "success"


def test_codex_generate_patch_doc_exists():
    doc = PROJECT_ROOT / "docs" / "codex-generate-patch.md"

    assert doc.exists()
    content = doc.read_text(encoding="utf-8")
    assert "repair_request.json" in content
    assert "patch.json" in content
    assert "python -m code_rpa repair validate" in content


def test_repo_skill_instructions_include_patch_rules():
    skill_doc = PROJECT_ROOT / ".agents" / "skills" / "self-healing-rpa-engineer" / "SKILL.md"
    content = skill_doc.read_text(encoding="utf-8")

    assert "Generate a selector-only `patch.json`" in content
    assert "python -m code_rpa repair validate <repair_request_path> <patch_path>" in content
    assert "python -m code_rpa repair sandbox <repair_request_path> <patch_path>" in content
    assert "python -m code_rpa repair apply <repair_request_path> <patch_path>" in content
