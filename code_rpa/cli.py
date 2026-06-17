"""Minimal CLI for the Self-Healing Code RPA framework."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from repair_agent.patch_validator import PatchValidator
from skill_registry.registry import SkillRegistry
from skill_registry.version_manager import VersionManager


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

    repair_parser = subparsers.add_parser("repair")
    repair_sub = repair_parser.add_subparsers(dest="action")
    repair_validate = repair_sub.add_parser("validate")
    repair_validate.add_argument("repair_request_path")
    repair_validate.add_argument("patch_path")

    version_parser = subparsers.add_parser("version")
    version_sub = version_parser.add_subparsers(dest="action")
    version_list = version_sub.add_parser("list")
    version_list.add_argument("skill_id")
    version_rollback = version_sub.add_parser("rollback")
    version_rollback.add_argument("skill_id")
    version_rollback.add_argument("version_id")

    return parser


def handle_skill(args: argparse.Namespace, project_root: Path) -> int:
    registry = SkillRegistry(project_root / "example_skills")

    if args.action == "list":
        for skill_id in registry.list_skill_ids():
            print(skill_id)
        return 0

    if args.action == "create":
        create_skill(project_root, args.skill_id)
        print(f"created example_skills/{args.skill_id}")
        return 0

    if args.action == "run":
        result = run_skill(project_root, args.skill_id)
        print(result)
        return 0

    if args.action == "test":
        return test_skill(project_root, args.skill_id)

    return 1


def handle_repair(args: argparse.Namespace, project_root: Path) -> int:
    repair_request = read_json(Path(args.repair_request_path))
    skill_id = repair_request["skill_id"]
    skill = SkillRegistry(project_root / "example_skills").load(skill_id)
    validator = PatchValidator()
    result = validator.validate_patch_file(
        args.repair_request_path,
        args.patch_path,
        current_skill=skill,
    )
    if result.is_valid:
        print("valid")
        return 0
    print("invalid")
    for error in result.errors:
        print(error)
    return 1


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


def create_skill(project_root: Path, skill_id: str) -> None:
    validate_skill_id(skill_id)
    skill_dir = project_root / "example_skills" / skill_id
    if skill_dir.exists():
        raise SystemExit(f"Skill already exists: {skill_id}")

    skill_dir.mkdir(parents=True)
    tests_dir = skill_dir / "tests"
    tests_dir.mkdir()

    skill_name = title_from_skill_id(skill_id)
    assets_dir = project_root / ".agents" / "skills" / "self-healing-rpa-engineer" / "assets"
    write_template(assets_dir / "skill.yaml.template", skill_dir / "skill.yaml", skill_id, skill_name)
    write_template(assets_dir / "selectors.yaml.template", skill_dir / "selectors.yaml", skill_id, skill_name)
    write_template(assets_dir / "repair_policy.yaml.template", skill_dir / "repair_policy.yaml", skill_id, skill_name)
    (skill_dir / "main.py").write_text(main_py_template(skill_id), encoding="utf-8")
    (tests_dir / "test_skill.py").write_text(test_skill_template(skill_id), encoding="utf-8")


def run_skill(project_root: Path, skill_id: str) -> dict[str, Any]:
    module = load_skill_main(project_root, skill_id)
    result = module.run(storage_root=project_root / "storage")
    return result.to_dict()


def test_skill(project_root: Path, skill_id: str) -> int:
    skill_test_dir = project_root / "example_skills" / skill_id / "tests"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(skill_test_dir)],
        cwd=project_root,
        check=False,
    )
    return completed.returncode


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


def write_template(template_path: Path, target_path: Path, skill_id: str, skill_name: str) -> None:
    rendered = template_path.read_text(encoding="utf-8").format(
        skill_id=skill_id,
        skill_name=skill_name,
    )
    target_path.write_text(rendered, encoding="utf-8")


def main_py_template(skill_id: str) -> str:
    return f'''"""Entrypoint for the {skill_id} Skill."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rpa_runtime.browser import PlaywrightBrowser
from rpa_runtime.executor import RPAExecutor, RunResult
from skill_registry.loader import SkillLoader


def run(page: Any | None = None, storage_root: Path | None = None) -> RunResult:
    skill_path = Path(__file__).with_name("skill.yaml")
    skill = SkillLoader().load(skill_path)
    executor = RPAExecutor(
        storage_root=storage_root or PROJECT_ROOT / "storage",
        browser=PlaywrightBrowser(headless=True),
    )
    return executor.run(skill, page=page)


if __name__ == "__main__":
    print(run().to_dict())
'''


def test_skill_template(skill_id: str) -> str:
    return f'''from pathlib import Path
import importlib.util


SKILL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("{skill_id}_main", SKILL_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_skill_loads(tmp_path):
    result = module.run(storage_root=tmp_path)
    assert result.skill_id == "{skill_id}"
'''


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

