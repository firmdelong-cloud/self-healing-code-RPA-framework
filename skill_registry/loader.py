"""YAML skill loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rpa_runtime.exceptions import SkillLoadError


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    version: str
    base_path: Path
    entrypoint: str
    selectors_path: Path
    repair_policy_path: Path
    selectors: dict[str, Any]
    repair_policy: dict[str, Any]
    steps: list[dict[str, Any]]
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

        required = ["id", "name", "version", "entrypoint", "steps"]
        missing = [key for key in required if key not in raw]
        if missing:
            raise SkillLoadError(f"Skill is missing required fields: {missing}")

        selectors = self._read_yaml(selectors_path)
        repair_policy = self._read_yaml(repair_policy_path)

        return SkillDefinition(
            id=raw["id"],
            name=raw["name"],
            version=str(raw["version"]),
            base_path=base_path,
            entrypoint=raw["entrypoint"],
            selectors_path=selectors_path,
            repair_policy_path=repair_policy_path,
            selectors=selectors,
            repair_policy=repair_policy,
            steps=raw["steps"],
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

