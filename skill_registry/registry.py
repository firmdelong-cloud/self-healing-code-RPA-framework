"""Local skill registry."""

from __future__ import annotations

from pathlib import Path

from skill_registry.loader import SkillDefinition, SkillLoader


class SkillRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.loader = SkillLoader()

    def load(self, skill_id: str) -> SkillDefinition:
        skill_path = self.root / skill_id / "skill.yaml"
        return self.loader.load(skill_path)

    def list_skill_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and (child / "skill.yaml").exists()
        )

