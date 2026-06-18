"""YAML skill loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rpa_runtime.exceptions import SkillLoadError
from skill_core.skill_schema import SkillKind, normalize_skill_kind


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    skill_id: str
    name: str
    version: str
    skill_type: SkillKind
    runtime: str
    base_path: Path
    entrypoint: str
    selectors_path: Path
    repair_policy_path: Path
    description: str
    inputs: dict[str, Any]
    variables: dict[str, Any]
    output_schema: dict[str, Any]
    policy: dict[str, Any]
    policies: dict[str, Any]
    selectors: dict[str, Any]
    repair_policy: dict[str, Any]
    steps: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    tests: list[str]
    raw: dict[str, Any]


class SkillLoader:
    def load(self, skill_yaml_path: str | Path) -> SkillDefinition:
        path = Path(skill_yaml_path).resolve()
        if not path.exists():
            raise SkillLoadError(f"Skill file does not exist: {path}")

        raw = self._read_yaml(path)
        base_path = path.parent

        selectors_path = base_path / raw.get("selectors", "selectors.yaml")
        repair_policy_path = base_path / raw.get("repair_policy", "repair_policy.yaml")

        skill_id = raw.get("skill_id", raw.get("id"))
        workflow_nodes = raw.get("nodes", []) or []
        legacy_steps = raw.get("steps", []) or []

        required = ["name", "version"]
        missing = [key for key in required if key not in raw]
        if not skill_id:
            missing.append("skill_id")
        if "entrypoint" not in raw:
            missing.append("entrypoint")
        if not workflow_nodes and not legacy_steps:
            missing.append("nodes")
        if missing:
            raise SkillLoadError(f"Skill is missing required fields: {missing}")

        selectors = self._read_yaml(selectors_path)
        repair_policy = self._read_yaml(repair_policy_path)

        return SkillDefinition(
            id=str(skill_id),
            skill_id=str(skill_id),
            name=raw["name"],
            version=str(raw["version"]),
            skill_type=normalize_skill_kind(raw.get("type")),
            runtime=str(raw.get("runtime", "web")),
            base_path=base_path,
            entrypoint=raw["entrypoint"],
            selectors_path=selectors_path,
            repair_policy_path=repair_policy_path,
            description=str(raw.get("description", "")),
            inputs=raw.get("inputs", {}) or {},
            variables=raw.get("variables", {}) or {},
            output_schema=raw.get("outputs", {}) or {},
            policy=raw.get("policies", raw.get("policy", {})) or {},
            policies=raw.get("policies", raw.get("policy", {})) or {},
            selectors=selectors,
            repair_policy=repair_policy,
            steps=legacy_steps,
            nodes=workflow_nodes,
            edges=raw.get("edges", []) or [],
            tests=raw.get("tests", []) or [],
            raw=raw,
        )

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise SkillLoadError(f"YAML file does not exist: {path}")
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise SkillLoadError(f"YAML root must be a mapping: {path}")
        return data
