"""Filesystem-backed skill versioning with activation and rollback."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re
import shutil

import yaml

from skill_registry.loader import SkillDefinition


class VersionManager:
    def __init__(self, versions_root: Path):
        self.versions_root = versions_root
        self.versions_root.mkdir(parents=True, exist_ok=True)

    def snapshot(self, skill: SkillDefinition, reason: str = "manual") -> Path:
        metadata = {
            "created_at": self._timestamp_iso(),
            "skill_id": skill.id,
            "patch_id": None,
            "base_version": skill.version,
            "test_result": None,
            "changed_files": [],
            "reason": reason,
            "skill_version": skill.version,
            "version_label": skill.version,
        }
        version_dir = self._create_version_dir(skill.id, skill.version, reason)
        self._copy_skill_tree(skill.base_path, version_dir)
        self._write_metadata(version_dir, metadata)
        self._set_current(skill.id, version_dir.name)
        return version_dir

    def create_new_version(
        self,
        *,
        skill: SkillDefinition,
        patched_skill_path: str | Path,
        patch: dict[str, Any],
        test_result: Any,
    ) -> Path:
        if not getattr(test_result, "success", False):
            raise ValueError("Cannot create a new version from a failed sandbox test result")

        patched_skill_path = Path(patched_skill_path)
        new_version = self._next_version(patch.get("base_version", skill.version))
        self._update_skill_yaml_version(patched_skill_path / "skill.yaml", new_version)

        version_dir = self._create_version_dir(skill.id, new_version, patch.get("patch_id", "patch"))
        self._copy_skill_tree(patched_skill_path, version_dir)

        metadata = {
            "created_at": self._timestamp_iso(),
            "skill_id": skill.id,
            "patch_id": patch.get("patch_id"),
            "base_version": patch.get("base_version", skill.version),
            "test_result": {
                "success": getattr(test_result, "success", False),
                "stdout": getattr(test_result, "stdout", ""),
                "stderr": getattr(test_result, "stderr", ""),
                "duration": getattr(test_result, "duration", 0.0),
                "test_command": getattr(test_result, "test_command", []),
            },
            "changed_files": [patch.get("selector_changes", {}).get("target_file")],
            "reason": patch.get("reason"),
            "skill_version": new_version,
            "version_label": new_version,
            "patch_type": patch.get("patch_type"),
        }
        self._write_metadata(version_dir, metadata)

        self._replace_live_skill(skill.base_path, version_dir)
        self._set_current(skill.id, version_dir.name)
        return version_dir

    def list_versions(self, skill_id: str) -> list[dict[str, Any]]:
        root = self._skill_versions_root(skill_id)
        if not root.exists():
            return []

        versions: list[dict[str, Any]] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            metadata_path = child / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["version_id"] = child.name
                versions.append(metadata)
        versions.sort(key=lambda item: item["created_at"])
        return versions

    def get_current_version(self, skill_id: str) -> dict[str, Any] | None:
        current_path = self._skill_versions_root(skill_id) / "current.json"
        if not current_path.exists():
            return None
        data = json.loads(current_path.read_text(encoding="utf-8"))
        version_id = data["version_id"]
        metadata_path = self._skill_versions_root(skill_id) / version_id / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["version_id"] = version_id
        return metadata

    def rollback_to_version(self, *, skill: SkillDefinition, version_id: str) -> Path:
        version_dir = self._skill_versions_root(skill.id) / version_id
        if not version_dir.exists():
            raise ValueError(f"Version does not exist: {version_id}")
        self._replace_live_skill(skill.base_path, version_dir)
        self._set_current(skill.id, version_id)
        return version_dir

    def _create_version_dir(self, skill_id: str, version_label: str, reason: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        safe_reason = re.sub(r"[^A-Za-z0-9_-]+", "_", str(reason or "manual")).strip("_") or "manual"
        version_dir = self._skill_versions_root(skill_id) / f"{version_label}__{timestamp}__{safe_reason}"
        version_dir.mkdir(parents=True, exist_ok=False)
        return version_dir

    def _skill_versions_root(self, skill_id: str) -> Path:
        root = self.versions_root / skill_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _copy_skill_tree(self, source: Path, destination: Path) -> None:
        for item in source.iterdir():
            if item.name in {".git", "__pycache__"}:
                continue
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(item, target)

    def _replace_live_skill(self, live_skill_path: Path, version_dir: Path) -> None:
        backup_dir = live_skill_path.parent / f"{live_skill_path.name}.rollback_tmp"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if live_skill_path.exists():
            live_skill_path.rename(backup_dir)

        try:
            live_skill_path.mkdir(parents=True, exist_ok=True)
            for item in version_dir.iterdir():
                if item.name == "metadata.json":
                    continue
                target = live_skill_path / item.name
                if item.is_dir():
                    shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(item, target)
        finally:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

    def _write_metadata(self, version_dir: Path, metadata: dict[str, Any]) -> None:
        (version_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _set_current(self, skill_id: str, version_id: str) -> None:
        current_path = self._skill_versions_root(skill_id) / "current.json"
        payload = {"version_id": version_id, "updated_at": self._timestamp_iso()}
        current_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _next_version(self, base_version: str) -> str:
        parts = base_version.split(".")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            major, minor, patch = (int(part) for part in parts)
            return f"{major}.{minor}.{patch + 1}"
        return f"{base_version}.1"

    def _timestamp_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _update_skill_yaml_version(self, skill_yaml_path: Path, new_version: str) -> None:
        data = yaml.safe_load(skill_yaml_path.read_text(encoding="utf-8")) or {}
        data["version"] = new_version
        skill_yaml_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
