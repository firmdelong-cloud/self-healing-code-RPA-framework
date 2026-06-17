from pathlib import Path
import json
import shutil

import yaml

from code_rpa.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_project(tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target


def test_cli_skill_list_shows_web_report_export(capsys):
    exit_code = main(["--project-root", str(PROJECT_ROOT), "skill", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "web_report_export" in captured.out


def test_cli_skill_create_generates_standard_skill_files(tmp_path):
    project = copy_project(tmp_path)

    exit_code = main(["--project-root", str(project), "skill", "create", "invoice_export"])

    skill_dir = project / "example_skills" / "invoice_export"
    skill_yaml = yaml.safe_load((skill_dir / "skill.yaml").read_text(encoding="utf-8"))
    selectors_yaml = yaml.safe_load((skill_dir / "selectors.yaml").read_text(encoding="utf-8"))
    repair_policy_yaml = yaml.safe_load((skill_dir / "repair_policy.yaml").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (skill_dir / "skill.yaml").exists()
    assert (skill_dir / "selectors.yaml").exists()
    assert (skill_dir / "repair_policy.yaml").exists()
    assert (skill_dir / "main.py").exists()
    assert (skill_dir / "tests" / "test_skill.py").exists()
    assert skill_yaml["id"] == "invoice_export"
    assert skill_yaml["name"] == "Invoice Export"
    assert skill_yaml["version"] == "0.1.0"
    assert "description" in skill_yaml
    assert "inputs" in skill_yaml
    assert "steps" in skill_yaml
    assert "primary" in selectors_yaml["submit_button"]
    assert "fallbacks" in selectors_yaml["submit_button"]
    assert repair_policy_yaml["repair_scope"]["scope_type"] == "selector_only"


def test_cli_repair_validate_accepts_legal_patch(tmp_path, capsys):
    repair_request_path, patch_path = write_repair_files(tmp_path)

    exit_code = main([
        "--project-root",
        str(PROJECT_ROOT),
        "repair",
        "validate",
        str(repair_request_path),
        str(patch_path),
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "valid" in captured.out


def test_cli_repair_sandbox_runs_valid_patch(tmp_path, capsys):
    project = copy_project(tmp_path)
    repair_request_path, patch_path = write_repair_files(tmp_path)

    exit_code = main([
        "--project-root",
        str(project),
        "repair",
        "sandbox",
        str(repair_request_path),
        str(patch_path),
    ])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["success"] is True
    assert "patched_skill_path" in payload


def test_repo_skill_files_exist():
    skill_root = PROJECT_ROOT / ".agents" / "skills" / "self-healing-rpa-engineer"

    assert (skill_root / "SKILL.md").exists()
    assert (skill_root / "references" / "architecture.md").exists()
    assert (skill_root / "references" / "rpa-skill-spec.md").exists()
    assert (skill_root / "references" / "patch-json-spec.md").exists()
    assert (skill_root / "references" / "repair-pipeline.md").exists()
    assert (skill_root / "assets" / "skill.yaml.template").exists()
    assert (skill_root / "assets" / "selectors.yaml.template").exists()
    assert (skill_root / "assets" / "repair_policy.yaml.template").exists()


def test_readme_contains_key_sections():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    required_phrases = [
        "Self-Healing Code RPA Framework",
        "Quick Start",
        "What This Is Not",
        "Architecture",
        "MVP Scope",
        "Install",
        "Run Demo",
        "Run Tests",
        "CLI Usage",
        "Create a New Skill",
        "Repair Pipeline",
        "Rollback",
        "Codex Repo Skill",
        "Current Limitations",
        "repair_request.json",
        "patch.json",
        "Sandbox Testing",
        "Safety Boundaries",
    ]
    for phrase in required_phrases:
        assert phrase in readme


def write_repair_files(tmp_path: Path) -> tuple[Path, Path]:
    repair_request = {
        "run_id": "test-run",
        "skill_id": "web_report_export",
        "skill_name": "Web Report Export",
        "skill_version": "0.2.0",
        "failed_step_id": "click_export",
        "failed_step_goal": "Click the export button to generate the report.",
        "risk_level": "medium",
        "allowed_repair_scope": {
            "scope_type": "selector_only",
            "failed_step_id": "click_export",
            "allowed_files": ["example_skills/web_report_export/selectors.yaml"],
            "allowed_selector_refs": ["export_button"],
            "must_not_touch_other_steps": True,
            "must_not_touch_runtime": True,
        },
    }
    patch = {
        "patch_id": "cli-test-patch",
        "skill_id": "web_report_export",
        "skill_name": "Web Report Export",
        "base_version": "0.2.0",
        "target_step_id": "click_export",
        "patch_type": "fallback_selector_add",
        "selector_changes": {
            "target_file": "example_skills/web_report_export/selectors.yaml",
            "selector_ref": "export_button",
            "add_fallbacks": ["button[data-testid='export-button']"],
        },
        "code_changes": None,
        "allowed_repair_scope": repair_request["allowed_repair_scope"],
        "reason": "Add data-testid fallback for CLI validation.",
        "risk_level": "low",
        "test_command": ["python", "-m", "pytest", "tests/test_selector_resolver.py"],
        "created_at": "2026-06-17T00:00:00+00:00",
    }
    repair_request_path = tmp_path / "repair_request.json"
    patch_path = tmp_path / "patch.json"
    repair_request_path.write_text(json.dumps(repair_request, indent=2), encoding="utf-8")
    patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")
    return repair_request_path, patch_path
