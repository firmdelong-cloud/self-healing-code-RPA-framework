"""Static quality gate for RPA Skill directories."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import re

import yaml

from skill_core.skill_schema import SkillKind, SkillSchemaError, normalize_skill_kind


@dataclass(frozen=True)
class SkillValidationResult:
    skill_id: str
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillValidator:
    """Validate a Skill against the repository contract without running it."""

    REQUIRED_SKILL_FIELDS = {"name", "version", "description", "inputs"}
    ALLOWED_SKILL_TYPES = {kind.value for kind in SkillKind}
    REQUIRED_STEP_FIELDS = {"id", "type", "goal"}
    REQUIRED_NODE_FIELDS = {"id", "component", "goal"}
    SELECTOR_REF_REQUIRED_TYPES = {
        "click",
        "fill",
        "select",
        "extract_text",
        "extract_table",
        "download_file",
        "wait_for_selector",
        "detect_unread",
        "click_chat",
        "read_chat_text",
        "fill_text",
        "send_message",
    }
    OPTIONAL_SELECTOR_TYPES = {"wait_for", "assert_text"}
    SELECTOR_REFS_TYPES = {"login", "select_date_range"}
    PLACEHOLDER_PATTERN = re.compile(r"^\{\{([A-Z0-9_]+)\}\}$")

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.example_skills_root = self.project_root / "example_skills"
        self.fixtures_root = self.project_root / "tests" / "fixtures"

    def validate(self, skill_id: str) -> SkillValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        skill_dir = self.example_skills_root / skill_id

        if not skill_dir.exists():
            return self._result(skill_id, [f"Skill directory does not exist: example_skills/{skill_id}"], warnings)

        skill_yaml_path = skill_dir / "skill.yaml"
        selectors_path = skill_dir / "selectors.yaml"
        repair_policy_path = skill_dir / "repair_policy.yaml"

        self._require_file(skill_yaml_path, "skill.yaml", errors)
        self._require_file(selectors_path, "selectors.yaml", errors)
        self._require_file(repair_policy_path, "repair_policy.yaml", errors)

        skill_yaml = self._read_yaml(skill_yaml_path, errors)
        selectors_yaml = self._read_yaml(selectors_path, errors)
        repair_policy_yaml = self._read_yaml(repair_policy_path, errors)

        if skill_yaml:
            self._validate_skill_yaml(skill_id, skill_yaml, errors)
            self._validate_steps(skill_yaml, selectors_yaml, errors)
            self._validate_nodes(skill_yaml, selectors_yaml, errors)
            self._validate_fixtures(skill_id, skill_yaml, errors)

        if selectors_yaml:
            self._validate_selectors(selectors_yaml, errors, warnings)

        if repair_policy_yaml:
            self._validate_repair_policy(repair_policy_yaml, errors)

        self._validate_tests(skill_id, skill_dir, errors)
        return self._result(skill_id, errors, warnings)

    def _validate_skill_yaml(self, skill_id: str, data: dict[str, Any], errors: list[str]) -> None:
        try:
            skill_type = normalize_skill_kind(data.get("type"))
        except SkillSchemaError as error:
            errors.append(str(error))
            skill_type = SkillKind.PROCEDURE

        if skill_type != SkillKind.PROCEDURE:
            errors.append("example_skills currently accepts only type: procedure_skill")

        missing = sorted(field for field in self.REQUIRED_SKILL_FIELDS if field not in data)
        if missing:
            errors.append(f"skill.yaml is missing required fields: {missing}")

        declared_skill_id = data.get("skill_id", data.get("id"))
        if declared_skill_id != skill_id:
            errors.append(f"skill.yaml skill_id/id must match directory name '{skill_id}'")

        if "inputs" in data and not isinstance(data.get("inputs"), dict):
            errors.append("skill.yaml inputs must be a mapping")

        if "outputs" in data and not isinstance(data.get("outputs"), dict):
            errors.append("skill.yaml outputs must be a mapping")

        has_steps = isinstance(data.get("steps"), list) and bool(data.get("steps"))
        has_nodes = isinstance(data.get("nodes"), list) and bool(data.get("nodes"))
        if not has_steps and not has_nodes:
            errors.append("skill.yaml must define non-empty nodes or legacy steps")
        if "variables" in data and not isinstance(data.get("variables"), dict):
            errors.append("skill.yaml variables must be a mapping")
        if "policies" in data and not isinstance(data.get("policies"), dict):
            errors.append("skill.yaml policies must be a mapping")
        if "edges" in data and not isinstance(data.get("edges"), list):
            errors.append("skill.yaml edges must be a list")

        runtime = str(data.get("runtime", "web"))
        if runtime.startswith("desktop") and runtime != "desktop_mock":
            desktop_config = data.get("desktop")
            if not isinstance(desktop_config, dict):
                errors.append("desktop Skills must define a desktop mapping")
            elif not desktop_config.get("window_title_regex"):
                errors.append("desktop.window_title_regex is required for live desktop Skills")

    def _validate_steps(
        self,
        skill_yaml: dict[str, Any],
        selectors: dict[str, Any],
        errors: list[str],
    ) -> None:
        steps = skill_yaml.get("steps")
        if not isinstance(steps, list):
            return

        selector_refs = set(selectors.keys()) if isinstance(selectors, dict) else set()
        seen_step_ids: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"step[{index}] must be a mapping")
                continue

            step_id = str(step.get("id", f"step[{index}]"))
            missing = sorted(field for field in self.REQUIRED_STEP_FIELDS if field not in step)
            if missing:
                errors.append(f"step '{step_id}' is missing required fields: {missing}")

            if step_id in seen_step_ids:
                errors.append(f"duplicate step id: {step_id}")
            seen_step_ids.add(step_id)

            step_type = str(step.get("type", ""))
            if step_type in self.SELECTOR_REF_REQUIRED_TYPES:
                self._validate_selector_ref(step_id, step.get("selector_ref"), selector_refs, errors)
            elif step_type in self.OPTIONAL_SELECTOR_TYPES and step.get("selector_ref") is not None:
                self._validate_selector_ref(step_id, step.get("selector_ref"), selector_refs, errors)
            elif step_type in self.SELECTOR_REFS_TYPES:
                selector_refs_map = step.get("selector_refs")
                if not isinstance(selector_refs_map, dict) or not selector_refs_map:
                    errors.append(f"step '{step_id}' must define selector_refs")
                    continue
                for role, selector_ref in selector_refs_map.items():
                    self._validate_selector_ref(step_id, selector_ref, selector_refs, errors, role=str(role))

    def _validate_nodes(
        self,
        skill_yaml: dict[str, Any],
        selectors: dict[str, Any],
        errors: list[str],
    ) -> None:
        nodes = skill_yaml.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            return

        selector_refs = set(selectors.keys()) if isinstance(selectors, dict) else set()
        seen_node_ids: set[str] = set()
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"node[{index}] must be a mapping")
                continue

            node_id = str(node.get("id", f"node[{index}]"))
            missing = sorted(field for field in self.REQUIRED_NODE_FIELDS if field not in node)
            if missing:
                errors.append(f"node '{node_id}' is missing required fields: {missing}")

            if node_id in seen_node_ids:
                errors.append(f"duplicate node id: {node_id}")
            seen_node_ids.add(node_id)

            inputs = node.get("inputs", {}) or {}
            if not isinstance(inputs, dict):
                errors.append(f"node '{node_id}' inputs must be a mapping")
                continue

            component_id = str(node.get("component", ""))
            if component_id.startswith("browser.") and inputs.get("selector_ref"):
                self._validate_selector_ref(node_id, inputs.get("selector_ref"), selector_refs, errors)

        edge_ids = seen_node_ids
        for index, edge in enumerate(skill_yaml.get("edges", []) or []):
            if not isinstance(edge, dict):
                errors.append(f"edge[{index}] must be a mapping")
                continue
            if edge.get("from") not in edge_ids:
                errors.append(f"edge[{index}].from references missing node '{edge.get('from')}'")
            if edge.get("to") not in edge_ids:
                errors.append(f"edge[{index}].to references missing node '{edge.get('to')}'")

    def _validate_selector_ref(
        self,
        step_id: str,
        selector_ref: Any,
        selector_refs: set[str],
        errors: list[str],
        *,
        role: str | None = None,
    ) -> None:
        label = f"selector_refs.{role}" if role else "selector_ref"
        if not isinstance(selector_ref, str) or not selector_ref:
            errors.append(f"step '{step_id}' must define {label}")
            return
        if selector_ref not in selector_refs:
            errors.append(f"step '{step_id}' references missing selector '{selector_ref}'")

    def _validate_selectors(
        self,
        selectors: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if not isinstance(selectors, dict):
            errors.append("selectors.yaml root must be a mapping")
            return

        for selector_ref, selector_config in selectors.items():
            if not isinstance(selector_config, dict):
                errors.append(f"selector '{selector_ref}' must be a mapping")
                continue
            if not selector_config.get("primary"):
                errors.append(f"selector '{selector_ref}' must define primary")
            if not selector_config.get("fallbacks"):
                warnings.append(f"selector '{selector_ref}' has no fallback selectors")

    def _validate_repair_policy(self, policy: dict[str, Any], errors: list[str]) -> None:
        repair_scope = policy.get("repair_scope")
        if not isinstance(repair_scope, dict):
            errors.append("repair_policy.yaml must define repair_scope")
            return

        scope_type = str(repair_scope.get("scope_type", "")).lower()
        if scope_type == "code_changes" or repair_scope.get("code_changes") is not None:
            errors.append("repair_scope must not default to code_changes")
        if scope_type and scope_type != "selector_only":
            errors.append("repair_scope.scope_type must be selector_only for automatic repairs")

    def _validate_tests(self, skill_id: str, skill_dir: Path, errors: list[str]) -> None:
        candidate_paths = [
            skill_dir / "tests" / "test_skill.py",
            self.project_root / "tests" / f"test_{skill_id}.py",
        ]
        if not any(path.exists() for path in candidate_paths):
            errors.append(
                f"Skill tests are required at example_skills/{skill_id}/tests/test_skill.py "
                f"or tests/test_{skill_id}.py"
            )

    def _validate_fixtures(self, skill_id: str, skill_yaml: dict[str, Any], errors: list[str]) -> None:
        runtime = str(skill_yaml.get("runtime", "web"))
        expected_fixture_names = self._fixture_names_from_steps(skill_yaml.get("steps", []))
        expected_fixture_names.update(self._fixture_names_from_nodes(skill_yaml.get("nodes", [])))
        if runtime.startswith("desktop") and runtime != "desktop_mock" and not expected_fixture_names:
            return
        if not expected_fixture_names:
            errors.append("Skill must declare a local HTML fixture URL in skill.yaml")
            return

        for fixture_name in sorted(expected_fixture_names):
            fixture_path = self.fixtures_root / fixture_name
            if not fixture_path.exists():
                errors.append(f"Local HTML fixture is missing: tests/fixtures/{fixture_name}")

    def _fixture_names_from_steps(self, steps: Any) -> set[str]:
        fixture_names: set[str] = set()
        if not isinstance(steps, list):
            return fixture_names

        for step in steps:
            if not isinstance(step, dict):
                continue
            raw_url = step.get("url")
            if not isinstance(raw_url, str):
                continue
            if raw_url.startswith("file:") and raw_url.endswith(".html"):
                fixture_names.add(Path(raw_url).name)
                continue
            if raw_url.endswith(".html"):
                fixture_names.add(Path(raw_url).name)
                continue
            match = self.PLACEHOLDER_PATTERN.match(raw_url)
            if match:
                fixture_names.add(self._fixture_name_from_placeholder(match.group(1)))
        return fixture_names

    def _fixture_names_from_nodes(self, nodes: Any) -> set[str]:
        fixture_names: set[str] = set()
        if not isinstance(nodes, list):
            return fixture_names

        for node in nodes:
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {}) or {}
            if not isinstance(inputs, dict):
                continue
            raw_url = inputs.get("url")
            if not isinstance(raw_url, str):
                continue
            if raw_url.startswith("file:") and raw_url.endswith(".html"):
                fixture_names.add(Path(raw_url).name)
                continue
            if raw_url.endswith(".html"):
                fixture_names.add(Path(raw_url).name)
                continue
            match = self.PLACEHOLDER_PATTERN.match(raw_url)
            if match:
                fixture_names.add(self._fixture_name_from_placeholder(match.group(1)))
        return fixture_names

    def _fixture_name_from_placeholder(self, placeholder: str) -> str:
        name = placeholder.lower()
        for suffix in ("_fixture_url", "_url"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return f"{name}.html" if not name.endswith(".html") else name

    def _require_file(self, path: Path, label: str, errors: list[str]) -> None:
        if not path.exists():
            errors.append(f"{label} does not exist")

    def _read_yaml(self, path: Path, errors: list[str]) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            errors.append(f"{path.name} is not valid YAML: {error}")
            return {}
        if not isinstance(data, dict):
            errors.append(f"{path.name} root must be a mapping")
            return {}
        return data

    def _result(self, skill_id: str, errors: list[str], warnings: list[str]) -> SkillValidationResult:
        return SkillValidationResult(
            skill_id=skill_id,
            status="error" if errors else "ok",
            errors=errors,
            warnings=warnings,
        )
