import json
from pathlib import Path
import shutil

import pytest
import yaml

from example_skills.web_report_export.main import prepare_skill
from repair_agent.patch_validator import PatchValidator
from repair_agent.sandbox_runner import SandboxRunner
from rpa_runtime.executor import RPAExecutor
from skill_registry.loader import SkillLoader
from skill_registry.version_manager import VersionManager


class FakePage:
    def __init__(self, available_selectors=None):
        self.available_selectors = set(available_selectors or [])
        self.url = "about:blank"
        self.html = """
        <html>
          <body>
            <input id="username" />
            <input id="password" />
            <button id="login-submit">Sign in</button>
            <a id="report-page-link">Reports</a>
            <input id="date-start" />
            <input id="date-end" />
            <button data-testid="export-button">Export Report</button>
            <p id="export-success">Export ready</p>
          </body>
        </html>
        """

    def goto(self, url):
        self.url = url

    def click(self, selector):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")

    def fill(self, selector, value):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")

    def wait_for_selector(self, selector):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")

    def screenshot(self, path, full_page=True):
        Path(path).write_bytes(b"fake screenshot")

    def content(self):
        return self.html


def positive_selectors():
    return {
        "#username",
        "#password",
        "#login-submit",
        "#report-page-link",
        "#date-start",
        "#date-end",
        "button[data-testid='export-button']",
        "#export-success",
    }


def copy_project(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    target_root = tmp_path / "project_copy"
    shutil.copytree(
        source_root,
        target_root,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target_root


def degrade_export_selectors(project_root: Path) -> None:
    selectors_path = project_root / "example_skills" / "web_report_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    selectors["export_button"] = {
        "primary": "#export-button-primary-missing",
        "fallbacks": [],
    }
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")


def load_copied_skill(project_root: Path):
    skill_path = project_root / "example_skills" / "web_report_export" / "skill.yaml"
    fixture_url = (project_root / "tests" / "fixtures" / "report_demo.html").resolve().as_uri()
    return prepare_skill(SkillLoader().load(skill_path), fixture_url)


def run_failure_scenario(project_root: Path, storage_root: Path):
    skill = load_copied_skill(project_root)
    page = FakePage(available_selectors=positive_selectors())
    result = RPAExecutor(storage_root=storage_root).run(skill, page=page)
    repair_request = json.loads(Path(result.repair_request_path).read_text(encoding="utf-8"))
    return skill, result, repair_request


def valid_patch(skill, repair_request, test_command=None):
    return {
        "patch_id": "patch-export-fallback-001",
        "skill_id": skill.id,
        "skill_name": skill.name,
        "base_version": skill.version,
        "target_step_id": repair_request["failed_step_id"],
        "patch_type": "fallback_selector_add",
        "selector_changes": {
            "target_file": "example_skills/web_report_export/selectors.yaml",
            "selector_ref": "export_button",
            "add_fallbacks": ["button[data-testid='export-button']"],
        },
        "code_changes": None,
        "reason": "Add a stable data-testid fallback for the export button",
        "risk_level": "low",
        "test_command": test_command
        or [
            "python",
            "-m",
            "pytest",
            "tests/test_runtime.py::test_executor_runs_login_report_export_flow",
            "tests/test_runtime.py::test_click_export_primary_selector_fails_and_fallback_succeeds",
        ],
        "allowed_repair_scope": {
            "scope_type": "selector_only",
            "failed_step_id": repair_request["failed_step_id"],
            "allowed_files": ["example_skills/web_report_export/selectors.yaml"],
            "allowed_selector_refs": ["export_button"],
            "must_not_touch_other_steps": True,
            "must_not_touch_runtime": True,
        },
        "created_at": "2026-06-17T00:00:00+00:00",
    }


def read_export_fallbacks(project_root: Path) -> list[str]:
    selectors_path = project_root / "example_skills" / "web_report_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    return list(selectors["export_button"].get("fallbacks", []) or [])


def test_patch_validator_accepts_legal_fallback_patch(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, result, repair_request = run_failure_scenario(project_root, tmp_path / "storage")

    assert result.status == "failed"
    patch = valid_patch(skill, repair_request)
    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert validation.is_valid is True
    assert validation.errors == []


def test_patch_validator_rejects_patch_for_other_step(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")
    patch = valid_patch(skill, repair_request)
    patch["target_step_id"] = "enter_report_page"

    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert validation.is_valid is False
    assert any("target_step_id" in error for error in validation.errors)


def test_patch_validator_rejects_runtime_or_main_code_changes(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")
    patch = valid_patch(skill, repair_request)
    patch["code_changes"] = [{"target_file": "main.py", "replacement": "bad"}]

    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)

    assert validation.is_valid is False
    assert "code_changes must be null in phase two" in validation.errors


def test_patch_validator_rejects_ambiguous_or_runtime_target_files(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")

    ambiguous_patch = valid_patch(skill, repair_request)
    ambiguous_patch["selector_changes"]["target_file"] = "selectors.yaml"
    ambiguous_patch["allowed_repair_scope"]["allowed_files"] = ["selectors.yaml"]
    ambiguous_validation = PatchValidator().validate_patch(repair_request, ambiguous_patch, current_skill=skill)

    runtime_patch = valid_patch(skill, repair_request)
    runtime_patch["selector_changes"]["target_file"] = "repair_agent/patch_validator.py"
    runtime_patch["allowed_repair_scope"]["allowed_files"] = ["repair_agent/patch_validator.py"]
    runtime_validation = PatchValidator().validate_patch(repair_request, runtime_patch, current_skill=skill)

    assert ambiguous_validation.is_valid is False
    assert any("full relative path" in error for error in ambiguous_validation.errors)
    assert runtime_validation.is_valid is False
    assert any("allowed_files must match repair_request" in error for error in runtime_validation.errors)


def test_sandbox_failure_cannot_create_new_version(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")
    patch = valid_patch(skill, repair_request, test_command=["python", "-m", "pytest", "tests/does_not_exist.py"])

    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)
    assert validation.is_valid is True

    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=patch, project_root=project_root)
    version_manager = VersionManager(tmp_path / "versions")

    assert sandbox_result.success is False
    with pytest.raises(ValueError):
        version_manager.create_new_version(
            skill=skill,
            patched_skill_path=sandbox_result.patched_skill_path,
            patch=patch,
            test_result=sandbox_result,
        )
    assert version_manager.list_versions(skill.id) == []


def test_sandbox_success_creates_new_version_snapshot(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")
    patch = valid_patch(skill, repair_request)

    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)
    assert validation.is_valid is True

    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=patch, project_root=project_root)
    assert sandbox_result.success is True
    assert sandbox_result.duration > 0

    version_manager = VersionManager(tmp_path / "versions")
    version_dir = version_manager.create_new_version(
        skill=skill,
        patched_skill_path=sandbox_result.patched_skill_path,
        patch=patch,
        test_result=sandbox_result,
    )

    versions = version_manager.list_versions(skill.id)
    current = version_manager.get_current_version(skill.id)

    assert version_dir.exists()
    assert len(versions) == 1
    assert versions[0]["patch_id"] == patch["patch_id"]
    assert versions[0]["changed_files"] == ["example_skills/web_report_export/selectors.yaml"]
    assert versions[0]["test_result"]["success"] is True
    assert current["skill_version"] == "0.2.1"
    assert "button[data-testid='export-button']" in read_export_fallbacks(project_root)


def test_version_manager_can_rollback_to_previous_version(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, _, repair_request = run_failure_scenario(project_root, tmp_path / "storage")
    patch = valid_patch(skill, repair_request)

    version_manager = VersionManager(tmp_path / "versions")
    original_snapshot = version_manager.snapshot(skill, reason="before_patch")

    failed_again_before_patch = RPAExecutor(storage_root=tmp_path / "pre_patch_storage").run(
        load_copied_skill(project_root),
        page=FakePage(available_selectors=positive_selectors()),
    )
    assert failed_again_before_patch.status == "failed"
    assert failed_again_before_patch.steps[-1].step_id == "click_export"

    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=patch, project_root=project_root)
    assert sandbox_result.success is True
    version_manager.create_new_version(
        skill=skill,
        patched_skill_path=sandbox_result.patched_skill_path,
        patch=patch,
        test_result=sandbox_result,
    )
    assert "button[data-testid='export-button']" in read_export_fallbacks(project_root)

    repaired_run = RPAExecutor(storage_root=tmp_path / "post_patch_storage").run(
        load_copied_skill(project_root),
        page=FakePage(available_selectors=positive_selectors()),
    )
    assert repaired_run.status == "success"

    version_manager.rollback_to_version(skill=skill, version_id=original_snapshot.name)
    current = version_manager.get_current_version(skill.id)
    rolled_back_run = RPAExecutor(storage_root=tmp_path / "rolled_back_storage").run(
        load_copied_skill(project_root),
        page=FakePage(available_selectors=positive_selectors()),
    )

    assert read_export_fallbacks(project_root) == []
    assert current["version_id"] == original_snapshot.name
    assert rolled_back_run.status == "failed"
    assert rolled_back_run.steps[-1].step_id == "click_export"


def test_end_to_end_repair_loop_generates_patch_tests_and_recovers_skill(tmp_path):
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill, result, repair_request = run_failure_scenario(project_root, tmp_path / "storage")

    assert result.status == "failed"
    assert Path(result.repair_request_path).exists()

    patch = valid_patch(skill, repair_request)
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")

    validator = PatchValidator()
    validation = validator.validate_patch_file(
        result.repair_request_path,
        patch_path,
        current_skill=skill,
    )
    assert validation.is_valid is True

    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=patch, project_root=project_root)
    assert sandbox_result.success is True

    version_manager = VersionManager(tmp_path / "versions")
    version_manager.snapshot(skill, reason="pre_repair")
    version_manager.create_new_version(
        skill=skill,
        patched_skill_path=sandbox_result.patched_skill_path,
        patch=patch,
        test_result=sandbox_result,
    )

    repaired_skill = load_copied_skill(project_root)
    rerun_result = RPAExecutor(storage_root=tmp_path / "rerun_storage").run(
        repaired_skill,
        page=FakePage(available_selectors=positive_selectors()),
    )

    assert rerun_result.status == "success"
    assert version_manager.get_current_version(repaired_skill.id)["skill_version"] == "0.2.1"
