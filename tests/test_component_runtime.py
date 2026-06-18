from __future__ import annotations

import json
from pathlib import Path
import shutil

import yaml

from component_core import (
    ComponentContext,
    ComponentDefinition,
    ComponentRegistry,
    ComponentRunResult,
    ComponentRunner,
    default_component_registry,
)
from example_skills.report_export_and_summary.main import prepare_skill as prepare_summary_skill
from example_skills.web_report_export.main import prepare_skill as prepare_web_report_skill
from repair_agent.patch_validator import PatchValidator
from repair_agent.sandbox_runner import SandboxRunner
from rpa_runtime.executor import RPAExecutor
from skill_registry.loader import SkillLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ComponentFakePage:
    def __init__(self, available_selectors: set[str] | None = None):
        self.available_selectors = available_selectors or successful_selectors()
        self.url = "about:blank"
        self.clicked: list[str] = []
        self.filled: list[tuple[str, str]] = []
        self.waited: list[str] = []
        self.html = "<html><body><a id='download-link'>Download CSV</a></body></html>"

    def goto(self, url: str) -> None:
        self.url = url

    def click(self, selector: str) -> None:
        self._require(selector)
        self.clicked.append(selector)

    def fill(self, selector: str, value: str) -> None:
        self._require(selector)
        self.filled.append((selector, value))

    def wait_for_selector(self, selector: str, timeout: int | None = None) -> None:
        self._require(selector)
        self.waited.append(selector)

    def text_content(self, selector: str) -> str:
        self._require(selector)
        return "Download CSV"

    def get_attribute(self, selector: str, attribute: str) -> str:
        self._require(selector)
        if selector == "#download-link" and attribute == "href":
            return "data:text/csv,id,total%0A1,100"
        return ""

    def screenshot(self, path: str, full_page: bool = True) -> None:
        Path(path).write_bytes(b"fake screenshot")

    def content(self) -> str:
        return self.html

    def _require(self, selector: str) -> None:
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")


def successful_selectors() -> set[str]:
    return {
        "#username",
        "#password",
        "#login-submit",
        "#report-page-link",
        "#date-start",
        "#date-end",
        "button[data-testid='export-button']",
        "#export-success",
        "#download-link",
    }


def copy_project(tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target


def degrade_export_selectors(project_root: Path) -> None:
    selectors_path = project_root / "example_skills" / "web_report_export" / "selectors.yaml"
    selectors = yaml.safe_load(selectors_path.read_text(encoding="utf-8")) or {}
    selectors["export_button"] = {
        "primary": "#missing-export",
        "fallbacks": [],
    }
    selectors_path.write_text(yaml.safe_dump(selectors, sort_keys=False), encoding="utf-8")


def load_web_report(project_root: Path):
    skill = SkillLoader().load(project_root / "example_skills" / "web_report_export" / "skill.yaml")
    fixture_url = (project_root / "tests" / "fixtures" / "report_demo.html").resolve().as_uri()
    return prepare_web_report_skill(skill, fixture_url)


def test_component_registry_can_register_component(tmp_path: Path) -> None:
    registry = ComponentRegistry()

    registry.register(
        ComponentDefinition(
            id="test.echo",
            name="Echo",
            category="test",
            description="Return the input value.",
            inputs_schema={"value": "string"},
            outputs_schema={"value": "string"},
            errors=[],
            repairable=False,
            repair_scope="none",
            risk_level="low",
            run=lambda context, inputs: ComponentRunResult(outputs={"value": inputs["value"]}),
        )
    )

    assert registry.get("test.echo").id == "test.echo"
    assert "test.echo" in registry.list_component_ids()


def test_component_runner_can_execute_component(tmp_path: Path) -> None:
    context = ComponentContext(
        skill=type("Skill", (), {"id": "demo", "selectors": {}, "inputs": {}})(),
        run_id="run-1",
        storage_root=tmp_path,
    )
    runner = ComponentRunner(default_component_registry())

    result = runner.run_node(
        context,
        {
            "id": "write_file",
            "component": "file.write_text",
            "goal": "Write a file",
            "inputs": {"path": "hello.txt", "text": "hello", "output_key": "hello_path"},
        },
    )

    assert result.status == "success"
    assert Path(result.outputs["hello_path"]).read_text(encoding="utf-8") == "hello"
    assert context.outputs["hello_path"] == result.outputs["hello_path"]


def test_skill_dsl_can_be_loaded() -> None:
    skill = SkillLoader().load(PROJECT_ROOT / "example_skills" / "web_report_export" / "skill.yaml")

    assert skill.skill_id == "web_report_export"
    assert skill.nodes
    assert skill.edges
    assert skill.nodes[0]["component"] == "browser.goto"


def test_report_export_and_summary_skill_can_run(tmp_path: Path) -> None:
    skill = prepare_summary_skill(
        SkillLoader().load(PROJECT_ROOT / "example_skills" / "report_export_and_summary" / "skill.yaml"),
        (PROJECT_ROOT / "tests" / "fixtures" / "report_demo.html").resolve().as_uri(),
    )

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=ComponentFakePage())

    assert result.status == "success"
    assert result.outputs["table_rows"] == 1
    assert Path(result.outputs["csv_path"]).exists()
    assert "processed 1 data rows" in result.outputs["summary_text"]
    assert Path(result.outputs["summary_path"]).exists()


def test_failed_component_node_generates_repair_request(tmp_path: Path) -> None:
    skill = load_web_report(PROJECT_ROOT)
    skill.selectors["export_button"] = {"primary": "#missing-export", "fallbacks": []}

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=ComponentFakePage())

    assert result.status == "failed"
    repair_request = json.loads(Path(result.repair_request_path).read_text(encoding="utf-8"))
    assert repair_request["failed_component_node_id"] == "click_export"
    assert repair_request["failed_component_node"]["component_id"] == "browser.click"
    assert repair_request["failed_component_node"]["selector_ref"] == "export_button"
    assert repair_request["allowed_repair_scope"]["failed_component_node_id"] == "click_export"
    assert repair_request["allowed_repair_scope"]["allowed_selector_refs"] == ["export_button"]


def test_selector_patch_repairs_browser_click_component_node(tmp_path: Path) -> None:
    project_root = copy_project(tmp_path)
    degrade_export_selectors(project_root)
    skill = load_web_report(project_root)
    failed = RPAExecutor(storage_root=tmp_path / "storage").run(skill, page=ComponentFakePage())
    repair_request = json.loads(Path(failed.repair_request_path).read_text(encoding="utf-8"))
    patch = {
        "patch_id": "component-click-export-fallback",
        "skill_id": skill.id,
        "skill_name": skill.name,
        "base_version": skill.version,
        "target_component_node_id": "click_export",
        "patch_type": "fallback_selector_add",
        "selector_changes": {
            "target_file": "example_skills/web_report_export/selectors.yaml",
            "selector_ref": "export_button",
            "add_fallbacks": ["button[data-testid='export-button']"],
        },
        "code_changes": None,
        "reason": "Repair browser.click component node with selector fallback.",
        "risk_level": "low",
        "test_command": ["python", "-m", "pytest", "tests/test_runtime.py::test_click_export_primary_selector_fails_and_fallback_succeeds"],
        "allowed_repair_scope": {
            "scope_type": "selector_only",
            "failed_component_node_id": "click_export",
            "allowed_files": ["example_skills/web_report_export/selectors.yaml"],
            "allowed_selector_refs": ["export_button"],
            "must_not_touch_other_steps": True,
            "must_not_touch_runtime": True,
        },
        "created_at": repair_request["created_at"],
    }

    validation = PatchValidator().validate_patch(repair_request, patch, current_skill=skill)
    assert validation.is_valid is True

    SandboxRunner().apply_patch_to_project(project_root, patch)
    repaired = RPAExecutor(storage_root=tmp_path / "repaired_storage").run(
        load_web_report(project_root),
        page=ComponentFakePage(),
    )

    assert repaired.status == "success"
    assert next(step for step in repaired.steps if step.step_id == "click_export").selector_source == "fallback"
