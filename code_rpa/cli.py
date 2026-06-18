"""Minimal CLI for the Self-Healing Code RPA framework."""

from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from repair_agent.patch_validator import PatchValidator
from repair_agent.sandbox_runner import SandboxRunner
from rpa_runtime.executor import RPAExecutor
from skill_registry.registry import SkillRegistry
from skill_registry.loader import SkillLoader
from skill_registry.validator import SkillValidator
from skill_registry.version_manager import VersionManager

import yaml


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()

    if args.group == "skill":
        return handle_skill(args, project_root)
    if args.group == "repair":
        return handle_repair(args, project_root)
    if args.group == "version":
        return handle_version(args, project_root)
    if args.group == "desktop":
        return handle_desktop(args, project_root)
    if args.group == "doctor":
        return handle_doctor(project_root)
    if args.group == "demo":
        return handle_demo(args, project_root)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="code_rpa")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="group")

    skill_parser = subparsers.add_parser("skill")
    skill_sub = skill_parser.add_subparsers(dest="action")
    skill_sub.add_parser("list")
    skill_create = skill_sub.add_parser("create")
    skill_create.add_argument("skill_id")
    skill_run = skill_sub.add_parser("run")
    skill_run.add_argument("skill_id")
    skill_test = skill_sub.add_parser("test")
    skill_test.add_argument("skill_id")
    skill_validate = skill_sub.add_parser("validate")
    skill_validate.add_argument("skill_id")

    repair_parser = subparsers.add_parser("repair")
    repair_sub = repair_parser.add_subparsers(dest="action")
    repair_validate = repair_sub.add_parser("validate")
    repair_validate.add_argument("repair_request_path")
    repair_validate.add_argument("patch_path")
    repair_sandbox = repair_sub.add_parser("sandbox")
    repair_sandbox.add_argument("repair_request_path")
    repair_sandbox.add_argument("patch_path")
    repair_apply = repair_sub.add_parser("apply")
    repair_apply.add_argument("repair_request_path")
    repair_apply.add_argument("patch_path")

    version_parser = subparsers.add_parser("version")
    version_sub = version_parser.add_subparsers(dest="action")
    version_list = version_sub.add_parser("list")
    version_list.add_argument("skill_id")
    version_rollback = version_sub.add_parser("rollback")
    version_rollback.add_argument("skill_id")
    version_rollback.add_argument("version_id")

    desktop_parser = subparsers.add_parser("desktop")
    desktop_sub = desktop_parser.add_subparsers(dest="action")
    desktop_simulate = desktop_sub.add_parser("simulate")
    desktop_simulate.add_argument("skill_id")
    desktop_simulate.add_argument("--scenario", default="price")
    desktop_test = desktop_sub.add_parser("test")
    desktop_test.add_argument("skill_id")

    subparsers.add_parser("doctor")

    demo_parser = subparsers.add_parser("demo")
    demo_sub = demo_parser.add_subparsers(dest="action")
    demo_sub.add_parser("repair")
    demo_sub.add_parser("codex-patch")

    return parser


def handle_skill(args: argparse.Namespace, project_root: Path) -> int:
    registry = SkillRegistry(project_root / "example_skills")

    if args.action == "list":
        for skill_id in registry.list_skill_ids():
            print(skill_id)
        return 0

    if args.action == "create":
        created = create_skill(project_root, args.skill_id)
        print(json.dumps({
            "status": "ok",
            "skill_id": args.skill_id,
            "created": created,
            "next_commands": [
                f"python -m code_rpa skill validate {args.skill_id}",
                f"python -m code_rpa skill test {args.skill_id}",
            ],
        }, indent=2))
        return 0

    if args.action == "run":
        result = run_skill(project_root, args.skill_id)
        print(result)
        return 0

    if args.action == "test":
        return test_skill(project_root, args.skill_id)

    if args.action == "validate":
        return validate_skill(project_root, args.skill_id)

    return 1


def handle_repair(args: argparse.Namespace, project_root: Path) -> int:
    repair_request = read_json(Path(args.repair_request_path))
    patch = read_json(Path(args.patch_path))
    skill_id = repair_request["skill_id"]
    skill = SkillRegistry(project_root / "example_skills").load(skill_id)

    if args.action == "validate":
        validator = PatchValidator()
        result = validator.validate_patch_file(
            args.repair_request_path,
            args.patch_path,
            current_skill=skill,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.is_valid else 1

    if args.action == "sandbox":
        return run_repair_sandbox(project_root, skill, repair_request, patch, args)

    if args.action == "apply":
        payload = apply_repair_patch(
            project_root=project_root,
            repair_request_path=Path(args.repair_request_path),
            patch_path=Path(args.patch_path),
        )
        print(json.dumps(payload, indent=2))
        return 0 if payload["success"] else 1

    return 1


def run_repair_sandbox(
    project_root: Path,
    skill: Any,
    repair_request: dict[str, Any],
    patch: dict[str, Any],
    args: argparse.Namespace,
) -> int:
    validator = PatchValidator()
    validation = validator.validate_patch_file(
        args.repair_request_path,
        args.patch_path,
        current_skill=skill,
    )
    if not validation.is_valid:
        print(json.dumps(validation.to_dict(), indent=2))
        return 1

    runtime_patch = validator.normalize_for_runtime(repair_request, patch, current_skill=skill)
    result = SandboxRunner().run_patch(skill=skill, patch=runtime_patch, project_root=project_root)
    payload = {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration": result.duration,
        "patched_skill_path": result.patched_skill_path,
    }
    print(json.dumps(payload, indent=2))
    return 0 if result.success else 1


def apply_repair_patch(
    *,
    project_root: Path,
    repair_request_path: Path,
    patch_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    repair_request = read_json(repair_request_path)
    patch = read_json(patch_path)
    skill = SkillRegistry(project_root / "example_skills").load(repair_request["skill_id"])
    validator = PatchValidator()
    validation = validator.validate_patch(repair_request, patch, current_skill=skill)
    payload: dict[str, Any] = {
        "success": False,
        "validated": validation.is_valid,
        "sandbox_success": False,
        "version_id": None,
        "rerun_status": None,
        "errors": errors,
    }

    if not validation.is_valid:
        errors.extend(validation.errors)
        return payload

    runtime_patch = validator.normalize_for_runtime(repair_request, patch, current_skill=skill)
    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=runtime_patch, project_root=project_root)
    payload["sandbox_success"] = sandbox_result.success
    if not sandbox_result.success:
        errors.append("sandbox test failed")
        if sandbox_result.stderr:
            errors.append(sandbox_result.stderr)
        return payload

    version_manager = VersionManager(project_root / "storage" / "versions")
    version_manager.snapshot(skill, reason="pre_repair_apply")
    version_dir = version_manager.create_new_version(
        skill=skill,
        patched_skill_path=sandbox_result.patched_skill_path,
        patch=runtime_patch,
        test_result=sandbox_result,
    )
    payload["version_id"] = version_dir.name

    rerun_result = run_skill(project_root, skill.id)
    payload["rerun_status"] = rerun_result["status"]
    if rerun_result["status"] != "success":
        errors.append("rerun failed after applying repair")
        return payload

    payload["success"] = True
    return payload


def handle_version(args: argparse.Namespace, project_root: Path) -> int:
    manager = VersionManager(project_root / "storage" / "versions")

    if args.action == "list":
        for version in manager.list_versions(args.skill_id):
            print(version["version_id"])
        return 0

    if args.action == "rollback":
        skill = SkillRegistry(project_root / "example_skills").load(args.skill_id)
        manager.rollback_to_version(skill=skill, version_id=args.version_id)
        print(f"rolled back {args.skill_id} to {args.version_id}")
        return 0

    return 1


def handle_desktop(args: argparse.Namespace, project_root: Path) -> int:
    registry = SkillRegistry(project_root / "example_skills")
    skill = registry.load(args.skill_id)
    if not skill.runtime.startswith("desktop"):
        print(json.dumps({
            "status": "error",
            "error": f"Skill '{args.skill_id}' is not a desktop runtime Skill.",
        }, indent=2))
        return 1

    if args.action == "simulate":
        simulate_storage = Path(tempfile.mkdtemp(prefix="code_rpa_desktop_simulate_"))
        result = run_desktop_skill(
            project_root,
            args.skill_id,
            scenario=getattr(args, "scenario", "price"),
            storage_root=simulate_storage,
        )
        payload = {"status": result["status"], **result["outputs"]}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if result["status"] == "success" else 1

    if args.action == "test":
        return test_skill(project_root, args.skill_id)

    return 1


def handle_doctor(project_root: Path) -> int:
    checks = [
        check_python_version(),
        check_project_root(project_root),
        check_import("playwright", "Playwright import"),
        check_import("pytest", "pytest import"),
        check_path(project_root / "example_skills", "example_skills exists"),
        check_path(project_root / "storage", "storage exists"),
        check_registry(project_root),
    ]
    payload = {
        "status": "ok" if all(check["ok"] for check in checks) else "failed",
        "project_root": str(project_root),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 1


def handle_demo(args: argparse.Namespace, project_root: Path) -> int:
    if args.action == "repair":
        payload = run_demo_repair(project_root)
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("success") else 1
    if args.action == "codex-patch":
        payload = run_demo_codex_patch(project_root)
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("success") else 1
    return 1


def run_demo_repair(project_root: Path) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix="code_rpa_demo_repair_")) / project_root.name
    shutil.copytree(
        project_root,
        temp_root,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    degrade_demo_export_selector(temp_root)

    skill_path = temp_root / "example_skills" / "web_report_export" / "skill.yaml"
    skill = prepare_demo_skill(temp_root, SkillLoader().load(skill_path))
    page = DemoRepairPage()
    failure_result = RPAExecutor(storage_root=temp_root / "storage").run(skill, page=page)
    if failure_result.status != "failed" or not failure_result.repair_request_path:
        return {
            "success": False,
            "message": "repair demo did not produce the expected failure",
            "project_copy": str(temp_root),
        }

    repair_request = read_json(Path(failure_result.repair_request_path))
    patch = build_demo_patch(skill, repair_request)
    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)
    if not validation.is_valid:
        return {
            "success": False,
            "message": "mock patch failed validation",
            "errors": validation.errors,
            "project_copy": str(temp_root),
        }

    sandbox_result = SandboxRunner().run_patch(skill=skill, patch=patch, project_root=temp_root)
    if not sandbox_result.success:
        return {
            "success": False,
            "message": "sandbox test failed",
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "project_copy": str(temp_root),
        }

    version_manager = VersionManager(temp_root / "storage" / "versions")
    version_manager.snapshot(skill, reason="demo_pre_repair")
    version_dir = version_manager.create_new_version(
        skill=skill,
        patched_skill_path=sandbox_result.patched_skill_path,
        patch=patch,
        test_result=sandbox_result,
    )

    repaired_skill = prepare_demo_skill(temp_root, SkillLoader().load(skill_path))
    rerun_result = RPAExecutor(storage_root=temp_root / "storage").run(repaired_skill, page=DemoRepairPage())

    return {
        "success": rerun_result.status == "success",
        "message": "repair demo success" if rerun_result.status == "success" else "repair demo rerun failed",
        "failed_step_id": repair_request["failed_step_id"],
        "repair_request_path": failure_result.repair_request_path,
        "sandbox_success": sandbox_result.success,
        "version_id": version_dir.name,
        "rerun_status": rerun_result.status,
        "project_copy": str(temp_root),
    }


def run_demo_codex_patch(project_root: Path) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix="code_rpa_demo_codex_patch_")) / project_root.name
    shutil.copytree(
        project_root,
        temp_root,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    degrade_customer_keyword_selector(temp_root)

    skill_path = temp_root / "example_skills" / "customer_search_export" / "skill.yaml"
    skill = prepare_customer_skill(temp_root, SkillLoader().load(skill_path))
    failure_result = RPAExecutor(storage_root=temp_root / "storage").run(skill, page=DemoCustomerPage())
    if failure_result.status != "failed" or not failure_result.repair_request_path:
        return {
            "success": False,
            "message": "codex patch demo did not produce the expected failure",
            "project_copy": str(temp_root),
        }

    repair_request_path = Path(failure_result.repair_request_path)
    repair_request = read_json(repair_request_path)
    patch = build_codex_customer_patch(repair_request)
    patch_path = temp_root / "storage" / "repair_requests" / repair_request["run_id"] / "codex_patch.json"
    patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")

    apply_result = apply_repair_patch(
        project_root=temp_root,
        repair_request_path=repair_request_path,
        patch_path=patch_path,
    )
    return {
        "success": apply_result["success"],
        "message": "codex patch demo success" if apply_result["success"] else "codex patch demo failed",
        "failed_step_id": repair_request["failed_step_id"],
        "repair_request_path": str(repair_request_path),
        "patch_path": str(patch_path),
        "validated": apply_result["validated"],
        "sandbox_success": apply_result["sandbox_success"],
        "version_id": apply_result["version_id"],
        "rerun_status": apply_result["rerun_status"],
        "errors": apply_result["errors"],
        "project_copy": str(temp_root),
    }


def create_skill(project_root: Path, skill_id: str) -> dict[str, str]:
    validate_skill_id(skill_id)
    skill_dir = project_root / "example_skills" / skill_id
    if skill_dir.exists():
        raise SystemExit(f"Skill already exists: {skill_id}")

    skill_dir.mkdir(parents=True)
    tests_dir = skill_dir / "tests"
    tests_dir.mkdir()
    fixture_dir = project_root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    skill_name = title_from_skill_id(skill_id)
    fixture_placeholder = fixture_placeholder_for(skill_id)
    selector_ref = "page_title"
    assets_dir = project_root / ".agents" / "skills" / "self-healing-rpa-engineer" / "assets"
    write_template(
        assets_dir / "skill.yaml.template",
        skill_dir / "skill.yaml",
        skill_id,
        skill_name,
        fixture_placeholder,
        selector_ref,
    )
    write_template(
        assets_dir / "selectors.yaml.template",
        skill_dir / "selectors.yaml",
        skill_id,
        skill_name,
        fixture_placeholder,
        selector_ref,
    )
    write_template(
        assets_dir / "repair_policy.yaml.template",
        skill_dir / "repair_policy.yaml",
        skill_id,
        skill_name,
        fixture_placeholder,
        selector_ref,
    )
    (skill_dir / "main.py").write_text(main_py_template(skill_id, fixture_placeholder), encoding="utf-8")
    (tests_dir / "test_skill.py").write_text(test_skill_template(skill_id, fixture_placeholder), encoding="utf-8")
    (fixture_dir / f"{skill_id}.html").write_text(skill_fixture_template(skill_id, skill_name), encoding="utf-8")
    return {
        "skill_dir": str(skill_dir),
        "fixture_path": str(fixture_dir / f"{skill_id}.html"),
    }


def run_skill(project_root: Path, skill_id: str) -> dict[str, Any]:
    module = load_skill_main(project_root, skill_id)
    result = module.run(storage_root=project_root / "storage")
    return result.to_dict()


def run_desktop_skill(
    project_root: Path,
    skill_id: str,
    *,
    scenario: str = "price",
    storage_root: Path | None = None,
) -> dict[str, Any]:
    module = load_skill_main(project_root, skill_id)
    result = module.run(storage_root=storage_root or project_root / "storage", scenario=scenario)
    return result.to_dict()


def test_skill(project_root: Path, skill_id: str) -> int:
    skill_test_dir = project_root / "example_skills" / skill_id / "tests"
    root_test_file = project_root / "tests" / f"test_{skill_id}.py"
    pytest_targets: list[str] = []
    if skill_test_dir.exists():
        pytest_targets.append(str(skill_test_dir))
    if root_test_file.exists():
        pytest_targets.append(str(root_test_file))
    if not pytest_targets:
        pytest_targets.append(str(skill_test_dir))
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *pytest_targets],
        cwd=project_root,
        check=False,
    )
    return completed.returncode


def validate_skill(project_root: Path, skill_id: str) -> int:
    result = SkillValidator(project_root).validate(skill_id)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "ok" else 1


def load_skill_main(project_root: Path, skill_id: str) -> Any:
    main_path = project_root / "example_skills" / skill_id / "main.py"
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    spec = importlib.util.spec_from_file_location(f"{skill_id}_main", main_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load Skill entrypoint: {main_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_template(
    template_path: Path,
    target_path: Path,
    skill_id: str,
    skill_name: str,
    fixture_placeholder: str,
    selector_ref: str,
) -> None:
    rendered = template_path.read_text(encoding="utf-8").format(
        skill_id=skill_id,
        skill_name=skill_name,
        fixture_placeholder=fixture_placeholder,
        selector_ref=selector_ref,
    )
    target_path.write_text(rendered, encoding="utf-8")


def main_py_template(skill_id: str, fixture_placeholder: str) -> str:
    return f'''"""Entrypoint for the {skill_id} Skill."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from dataclasses import replace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rpa_runtime.browser import PlaywrightBrowser
from rpa_runtime.executor import RPAExecutor, RunResult
from skill_registry.loader import SkillLoader, SkillDefinition


FIXTURE_PLACEHOLDER = "{fixture_placeholder}"


def run(page: Any | None = None, storage_root: Path | None = None) -> RunResult:
    skill_path = Path(__file__).with_name("skill.yaml")
    skill = _prepare_skill(SkillLoader().load(skill_path))
    executor = RPAExecutor(
        storage_root=storage_root or PROJECT_ROOT / "storage",
        browser=PlaywrightBrowser(headless=True),
    )
    return executor.run(skill, page=page)


def _prepare_skill(skill: SkillDefinition) -> SkillDefinition:
    fixture_url = (PROJECT_ROOT / "tests" / "fixtures" / "{skill_id}.html").resolve().as_uri()
    resolved_steps = []
    for step in skill.steps:
        resolved_step = dict(step)
        if resolved_step.get("url") == chr(123) * 2 + FIXTURE_PLACEHOLDER + chr(125) * 2:
            resolved_step["url"] = fixture_url
        resolved_steps.append(resolved_step)
    return replace(skill, steps=resolved_steps)


if __name__ == "__main__":
    print(run().to_dict())
'''


def test_skill_template(skill_id: str, fixture_placeholder: str) -> str:
    return f'''from pathlib import Path
import importlib.util


SKILL_DIR = Path(__file__).resolve().parents[1]

from skill_registry.loader import SkillLoader


def test_skill_loads():
    skill = SkillLoader().load(SKILL_DIR / "skill.yaml")
    assert skill.id == "{skill_id}"
    assert skill.version == "0.1.0"
    assert "outputs" in skill.raw


def test_fixture_exists():
    assert (Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "{skill_id}.html").exists()
'''


def skill_fixture_template(skill_id: str, skill_name: str) -> str:
    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{skill_name}</title>
  </head>
  <body>
    <main>
      <h1 id="page-title" data-testid="page-title">{skill_name}</h1>
      <p id="page-body">Autogenerated fixture for {skill_id}.</p>
    </main>
  </body>
</html>
'''


def fixture_placeholder_for(skill_id: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in skill_id).upper()
    return f"{normalized}_FIXTURE_URL"


def validate_skill_id(skill_id: str) -> None:
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-.")
    if not skill_id or any(char not in allowed for char in skill_id):
        raise SystemExit("skill_id must contain lowercase letters, digits, '_', '-', or '.'")


def title_from_skill_id(skill_id: str) -> str:
    return " ".join(part.capitalize() for part in skill_id.replace("-", "_").split("_") if part)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return data


def check_python_version() -> dict[str, Any]:
    version = sys.version_info
    ok = (version.major, version.minor) >= (3, 11)
    return {
        "name": "Python version",
        "ok": ok,
        "details": f"{version.major}.{version.minor}.{version.micro}",
    }


def check_project_root(project_root: Path) -> dict[str, Any]:
    ok = (project_root / "rpa_runtime").exists() and (project_root / "skill_registry").exists()
    return {"name": "project root", "ok": ok, "details": str(project_root)}


def check_import(module_name: str, label: str) -> dict[str, Any]:
    try:
        __import__(module_name)
        return {"name": label, "ok": True, "details": module_name}
    except Exception as error:
        return {"name": label, "ok": False, "details": str(error)}


def check_path(path: Path, label: str) -> dict[str, Any]:
    return {"name": label, "ok": path.exists(), "details": str(path)}


def check_registry(project_root: Path) -> dict[str, Any]:
    try:
        registry = SkillRegistry(project_root / "example_skills")
        skill_ids = registry.list_skill_ids()
        loadable = [registry.load(skill_id).id for skill_id in skill_ids]
        return {"name": "registry loads", "ok": bool(loadable), "details": loadable}
    except Exception as error:
        return {"name": "registry loads", "ok": False, "details": str(error)}


def degrade_demo_export_selector(project_root: Path) -> None:
    selectors_path = project_root / "example_skills" / "web_report_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    selectors["export_button"] = {
        "primary": "#export-button-primary-missing",
        "fallbacks": [],
    }
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")


def degrade_customer_keyword_selector(project_root: Path) -> None:
    selectors_path = project_root / "example_skills" / "customer_search_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    selectors["customer_keyword_input"] = {
        "primary": "#missing-customer-keyword",
        "fallbacks": [],
    }
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")


def prepare_demo_skill(project_root: Path, skill: Any) -> Any:
    fixture_url = (project_root / "tests" / "fixtures" / "report_demo.html").resolve().as_uri()
    resolved_nodes = []
    for node in getattr(skill, "nodes", []) or []:
        resolved_node = dict(node)
        inputs = dict(resolved_node.get("inputs", {}) or {})
        if inputs.get("url") == "{{REPORT_DEMO_URL}}":
            inputs["url"] = fixture_url
            resolved_node["inputs"] = inputs
        resolved_nodes.append(resolved_node)

    resolved_steps = []
    for step in skill.steps:
        resolved_step = dict(step)
        if resolved_step.get("url") == "{{REPORT_DEMO_URL}}":
            resolved_step["url"] = fixture_url
        resolved_steps.append(resolved_step)
    return replace(skill, steps=resolved_steps, nodes=resolved_nodes)


def prepare_customer_skill(project_root: Path, skill: Any) -> Any:
    fixture_url = (project_root / "tests" / "fixtures" / "customer_demo.html").resolve().as_uri()
    resolved_steps = []
    for step in skill.steps:
        resolved_step = dict(step)
        if resolved_step.get("url") == "{{CUSTOMER_DEMO_URL}}":
            resolved_step["url"] = fixture_url
        resolved_steps.append(resolved_step)
    return replace(skill, steps=resolved_steps)


def build_demo_patch(skill: Any, repair_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "patch_id": "demo-repair-export-fallback",
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
        "reason": "Demo repair adds the stable data-testid fallback for the export button.",
        "risk_level": "low",
        "test_command": [
            "python",
            "-m",
            "pytest",
            "tests/test_runtime.py::test_executor_runs_login_report_export_flow",
            "tests/test_runtime.py::test_click_export_primary_selector_fails_and_fallback_succeeds",
        ],
        "allowed_repair_scope": repair_request["allowed_repair_scope"],
        "created_at": repair_request.get("created_at"),
    }


def build_codex_customer_patch(repair_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "repair_request_id": repair_request["run_id"],
        "skill_id": repair_request["skill_id"],
        "failed_step_id": repair_request["failed_step_id"],
        "scope": "selector_only",
        "changes": [
            {
                "file": "example_skills/customer_search_export/selectors.yaml",
                "selector_id": "customer_keyword_input",
                "field": "primary",
                "old": "#missing-customer-keyword",
                "new": "#customer-keyword",
            }
        ],
        "rationale": "The failure snapshot shows the keyword input selector changed; restore the primary selector to the stable input id.",
        "patch_id": "codex-customer-search-export-001",
        "risk_level": "low",
        "created_at": repair_request.get("created_at"),
        "test_command": repair_request.get("test_command", ["python", "-m", "pytest"]),
    }


class DemoRepairPage:
    def __init__(self):
        self.available_selectors = {
            "#username",
            "#password",
            "#login-submit",
            "#report-page-link",
            "#date-start",
            "#date-end",
            "button[data-testid='export-button']",
            "#export-success",
        }
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


class DemoCustomerPage:
    def __init__(self):
        self.available_selectors = {
            "#customer-keyword",
            "#search-customers",
            "#customer-results",
        }
        self.url = "about:blank"
        self.html = """
        <html>
          <body>
            <input id="customer-keyword" />
            <button id="search-customers">Search</button>
            <table id="customer-results">
              <thead>
                <tr><th>Customer ID</th><th>Name</th><th>Status</th></tr>
              </thead>
              <tbody>
                <tr><td>C-1001</td><td>Acme Logistics</td><td>Active</td></tr>
                <tr><td>C-1002</td><td>Acme Retail</td><td>Active</td></tr>
              </tbody>
            </table>
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
