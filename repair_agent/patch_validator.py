"""Validate selector-only repair patches before sandbox execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class PatchValidationResult:
    is_valid: bool
    reason: str
    errors: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    patch_scope: str = "selector_only"

    @property
    def allowed(self) -> bool:
        return self.is_valid

    @property
    def reasons(self) -> list[str]:
        return self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "changed_files": self.changed_files,
            "patch_scope": self.patch_scope,
        }


class PatchValidator:
    """Validate that a patch stays within the failed step and selector scope."""

    PATCH_TYPE_WHITELIST = {"selector_update", "fallback_selector_add"}
    PROTECTED_FILE_NAMES = {
        "main.py",
        "executor.py",
        "step_runner.py",
        "browser.py",
        "observer.py",
        "selector_resolver.py",
        "logger.py",
        "retry_policy.py",
        "README.md",
        "requirements.txt",
        "AGENTS.md",
    }
    PROTECTED_PATH_SEGMENTS = {
        "rpa_runtime",
        "repair_agent",
        "skill_registry",
        "tests",
        "docs",
        ".agents",
    }
    CODEX_PATCH_FIELDS = {"repair_request_id", "skill_id", "failed_step_id", "scope", "changes", "rationale"}

    def validate_patch_file(
        self,
        repair_request_path: str | Path,
        patch_path: str | Path,
        *,
        current_skill: Any | None = None,
    ) -> PatchValidationResult:
        repair_request = self._read_json(repair_request_path)
        patch = self._read_json(patch_path)
        return self.validate_patch(repair_request, patch, current_skill=current_skill)

    def validate_patch(
        self,
        repair_request: dict[str, Any],
        patch: dict[str, Any],
        *,
        current_skill: Any | None = None,
    ) -> PatchValidationResult:
        if self._is_codex_style_patch(patch):
            return self._validate_codex_style_patch(repair_request, patch, current_skill=current_skill)

        errors: list[str] = []

        failed_step_id = repair_request.get("failed_component_node_id") or repair_request.get("failed_step_id")
        allowed_scope = repair_request.get("allowed_repair_scope", {})
        expected_selector_refs = set(allowed_scope.get("allowed_selector_refs", []) or [])
        expected_failed_step_id = allowed_scope.get("failed_component_node_id") or allowed_scope.get("failed_step_id")
        expected_allowed_files = set(allowed_scope.get("allowed_files", []) or [])
        expected_skill_name = repair_request.get("skill_name")
        expected_skill_id = repair_request.get("skill_id")
        expected_version = repair_request.get("skill_version")
        repair_risk = str(repair_request.get("risk_level", "")).lower()
        patch_risk = str(patch.get("risk_level", "")).lower()
        patch_allowed_scope = patch.get("allowed_repair_scope")

        if patch.get("skill_name") != expected_skill_name:
            errors.append(
                f"patch skill_name must be '{expected_skill_name}', got '{patch.get('skill_name')}'"
            )

        if patch.get("skill_id") != expected_skill_id:
            errors.append(
                f"patch skill_id must be '{expected_skill_id}', got '{patch.get('skill_id')}'"
            )

        if patch.get("base_version") != expected_version:
            errors.append(
                f"patch base_version must be '{expected_version}', got '{patch.get('base_version')}'"
            )

        if current_skill is not None:
            if current_skill.id != patch.get("skill_id"):
                errors.append("patch skill_id does not match the current skill")
            if current_skill.name != patch.get("skill_name"):
                errors.append("patch skill_name does not match the current skill")
            if current_skill.version != patch.get("base_version"):
                errors.append("patch base_version does not match the current skill version")

        patch_target_id = patch.get("target_component_node_id") or patch.get("target_node_id") or patch.get("target_step_id")
        if patch_target_id != failed_step_id:
            errors.append(
                f"patch target_step_id must be '{failed_step_id}', got '{patch_target_id}'"
            )

        if patch_target_id != expected_failed_step_id:
            errors.append("patch target_step_id must match allowed_repair_scope.failed_step_id")

        if repair_risk == "high" or patch_risk == "high":
            errors.append("high-risk steps cannot be auto-patched")

        if patch.get("patch_type") not in self.PATCH_TYPE_WHITELIST:
            errors.append(f"patch_type must be one of {sorted(self.PATCH_TYPE_WHITELIST)}")

        if not isinstance(patch.get("reason"), str) or not patch.get("reason"):
            errors.append("patch reason is required")

        if str(patch.get("risk_level", "")).lower() not in {"low", "medium"}:
            errors.append("patch risk_level must be 'low' or 'medium'")

        test_command = patch.get("test_command")
        if not isinstance(test_command, list) or not test_command or not all(
            isinstance(item, str) for item in test_command
        ):
            errors.append("test_command must be a non-empty list of strings")
        elif test_command[:3] != ["python", "-m", "pytest"]:
            errors.append("test_command must start with ['python', '-m', 'pytest']")

        if "code_changes" not in patch or patch.get("code_changes") is not None:
            errors.append("code_changes must be null in phase two")

        if not isinstance(patch_allowed_scope, dict):
            errors.append("allowed_repair_scope must be an object")
        else:
            self._validate_allowed_scope(
                repair_scope=allowed_scope,
                patch_scope=patch_allowed_scope,
                errors=errors,
            )

        selector_changes = patch.get("selector_changes")
        if not isinstance(selector_changes, dict):
            errors.append("selector_changes must be an object")
        else:
            self._validate_selector_changes(
                selector_changes,
                patch_type=str(patch.get("patch_type")),
                expected_selector_refs=expected_selector_refs,
                expected_allowed_files=expected_allowed_files,
                errors=errors,
            )

        changed_files = []
        if isinstance(selector_changes, dict) and isinstance(selector_changes.get("target_file"), str):
            changed_files.append(selector_changes["target_file"].replace("\\", "/"))

        if errors:
            return PatchValidationResult(False, "Patch validation failed", errors, changed_files=changed_files)
        return PatchValidationResult(True, "Patch is safe to sandbox", changed_files=changed_files)

    def normalize_for_runtime(
        self,
        repair_request: dict[str, Any],
        patch: dict[str, Any],
        *,
        current_skill: Any | None = None,
    ) -> dict[str, Any]:
        """Convert a validated patch to the runtime patch shape used by SandboxRunner."""
        if not self._is_codex_style_patch(patch):
            return patch

        validation = self._validate_codex_style_patch(repair_request, patch, current_skill=current_skill)
        if not validation.is_valid:
            raise ValueError(f"Cannot normalize invalid patch: {validation.errors}")

        changes = patch["changes"]
        first_change = changes[0]
        field_name = first_change["field"]
        normalized: dict[str, Any] = {
            "patch_id": patch.get("patch_id") or patch.get("repair_request_id") or repair_request.get("run_id"),
            "skill_id": patch["skill_id"],
            "skill_name": repair_request.get("skill_name"),
            "base_version": repair_request.get("skill_version"),
            "target_step_id": patch.get("failed_component_node_id", patch["failed_step_id"]),
            "code_changes": None,
            "reason": patch.get("rationale", ""),
            "risk_level": str(patch.get("risk_level", "low")).lower(),
            "test_command": repair_request.get("test_command") or ["python", "-m", "pytest"],
            "allowed_repair_scope": repair_request.get("allowed_repair_scope", {}),
            "created_at": patch.get("created_at") or repair_request.get("created_at"),
        }

        selector_changes = {
            "target_file": first_change["file"].replace("\\", "/"),
            "selector_ref": first_change["selector_id"],
        }
        if field_name == "primary":
            normalized["patch_type"] = "selector_update"
            selector_changes["new_primary"] = first_change["new"]
        elif field_name == "fallbacks":
            if isinstance(first_change["new"], list):
                normalized["patch_type"] = "selector_update"
                selector_changes["new_fallbacks"] = first_change["new"]
            else:
                normalized["patch_type"] = "fallback_selector_add"
                selector_changes["add_fallbacks"] = [first_change["new"]]
        normalized["selector_changes"] = selector_changes
        return normalized

    def _validate_selector_changes(
        self,
        selector_changes: dict[str, Any],
        *,
        patch_type: str,
        expected_selector_refs: set[str],
        expected_allowed_files: set[str],
        errors: list[str],
    ) -> None:
        selector_ref = selector_changes.get("selector_ref")
        if selector_ref not in expected_selector_refs:
            errors.append(f"selector_changes.selector_ref must be in {sorted(expected_selector_refs)}")

        target_file = selector_changes.get("target_file")
        if not isinstance(target_file, str):
            errors.append("selector_changes.target_file must be a string")
            return

        if target_file == "selectors.yaml":
            errors.append("selector_changes.target_file must be a full relative path, not 'selectors.yaml'")

        if Path(target_file).is_absolute():
            errors.append("selector_changes.target_file must be a repository-relative path")

        normalized_target = target_file.replace("\\", "/")
        if normalized_target not in expected_allowed_files:
            errors.append("selector_changes.target_file must be present in allowed_repair_scope.allowed_files")

        if self._is_protected_target(normalized_target):
            errors.append("selector_changes.target_file must not touch runtime or repair framework code")

        raw_target = Path(normalized_target)
        if raw_target.name in self.PROTECTED_FILE_NAMES:
            errors.append(f"selector_changes cannot target protected file: {raw_target.name}")

        if patch_type == "selector_update":
            new_primary = selector_changes.get("new_primary")
            new_fallbacks = selector_changes.get("new_fallbacks")
            if new_primary is None and new_fallbacks is None:
                errors.append("selector_update must provide new_primary or new_fallbacks")
            if new_primary is not None and not isinstance(new_primary, str):
                errors.append("selector_changes.new_primary must be a string")
            if new_fallbacks is not None and (
                not isinstance(new_fallbacks, list) or not all(isinstance(item, str) for item in new_fallbacks)
            ):
                errors.append("selector_changes.new_fallbacks must be a list of strings")

        if patch_type == "fallback_selector_add":
            add_fallbacks = selector_changes.get("add_fallbacks")
            if not isinstance(add_fallbacks, list) or not add_fallbacks:
                errors.append("fallback_selector_add must provide a non-empty add_fallbacks list")
            elif not all(isinstance(item, str) for item in add_fallbacks):
                errors.append("selector_changes.add_fallbacks must be a list of strings")

    def _validate_allowed_scope(
        self,
        *,
        repair_scope: dict[str, Any],
        patch_scope: dict[str, Any],
        errors: list[str],
    ) -> None:
        required_values = {
            "scope_type": "selector_only",
            "must_not_touch_other_steps": True,
            "must_not_touch_runtime": True,
        }
        for key, expected in required_values.items():
            if patch_scope.get(key) != expected:
                errors.append(f"allowed_repair_scope.{key} must be {expected!r}")

        repair_files = sorted(repair_scope.get("allowed_files", []) or [])
        patch_files = sorted(patch_scope.get("allowed_files", []) or [])
        if patch_files != repair_files:
            errors.append("allowed_repair_scope.allowed_files must match repair_request")

        repair_refs = sorted(repair_scope.get("allowed_selector_refs", []) or [])
        patch_refs = sorted(patch_scope.get("allowed_selector_refs", []) or [])
        if patch_refs != repair_refs:
            errors.append("allowed_repair_scope.allowed_selector_refs must match repair_request")

        expected_node_id = repair_scope.get("failed_component_node_id") or repair_scope.get("failed_step_id")
        patch_node_id = patch_scope.get("failed_component_node_id") or patch_scope.get("failed_step_id")
        if patch_node_id != expected_node_id:
            errors.append("allowed_repair_scope.failed_step_id must match repair_request")

    def _validate_codex_style_patch(
        self,
        repair_request: dict[str, Any],
        patch: dict[str, Any],
        *,
        current_skill: Any | None = None,
    ) -> PatchValidationResult:
        errors: list[str] = []
        expected_skill_id = repair_request.get("skill_id")
        expected_failed_step_id = repair_request.get("failed_component_node_id") or repair_request.get("failed_step_id")
        expected_repair_request_id = repair_request.get("repair_request_id") or repair_request.get("run_id")
        allowed_scope = repair_request.get("allowed_repair_scope", {}) or {}
        expected_allowed_files = set(allowed_scope.get("allowed_files", []) or [])
        expected_selector_refs = set(allowed_scope.get("allowed_selector_refs", []) or [])
        changed_files: list[str] = []

        missing = sorted(field for field in self.CODEX_PATCH_FIELDS if field not in patch)
        if missing:
            errors.append(f"patch is missing required fields: {missing}")

        if patch.get("repair_request_id") != expected_repair_request_id:
            errors.append("repair_request_id must match repair_request.run_id")
        if patch.get("skill_id") != expected_skill_id:
            errors.append("skill_id must match repair_request.skill_id")
        patch_failed_id = patch.get("failed_component_node_id") or patch.get("failed_step_id")
        if patch_failed_id != expected_failed_step_id:
            errors.append("failed_step_id must match repair_request.failed_step_id")
        if patch.get("scope") != "selector_only":
            errors.append("scope must be selector_only")
        if current_skill is not None and patch.get("skill_id") != current_skill.id:
            errors.append("skill_id must match the current skill")
        if not isinstance(patch.get("rationale"), str) or not patch.get("rationale"):
            errors.append("rationale is required")

        changes = patch.get("changes")
        if not isinstance(changes, list) or not changes:
            errors.append("changes must be a non-empty list")
            changes = []
        elif len(changes) != 1:
            errors.append("phase six supports exactly one selector change per patch")

        for index, change in enumerate(changes):
            if not isinstance(change, dict):
                errors.append(f"changes[{index}] must be an object")
                continue
            self._validate_codex_change(
                change,
                index=index,
                expected_allowed_files=expected_allowed_files,
                expected_selector_refs=expected_selector_refs,
                changed_files=changed_files,
                errors=errors,
            )

        if errors:
            return PatchValidationResult(False, "Patch validation failed", errors, changed_files=sorted(set(changed_files)))
        return PatchValidationResult(True, "Patch is safe to sandbox", changed_files=sorted(set(changed_files)))

    def _validate_codex_change(
        self,
        change: dict[str, Any],
        *,
        index: int,
        expected_allowed_files: set[str],
        expected_selector_refs: set[str],
        changed_files: list[str],
        errors: list[str],
    ) -> None:
        required = {"file", "selector_id", "field", "old", "new"}
        missing = sorted(field for field in required if field not in change)
        if missing:
            errors.append(f"changes[{index}] is missing required fields: {missing}")

        target_file = change.get("file")
        if not isinstance(target_file, str):
            errors.append(f"changes[{index}].file must be a string")
            return
        normalized_target = target_file.replace("\\", "/")
        changed_files.append(normalized_target)

        if Path(normalized_target).is_absolute():
            errors.append(f"changes[{index}].file must be repository-relative")
        if normalized_target == "selectors.yaml":
            errors.append(f"changes[{index}].file must be a full relative selectors.yaml path")
        if normalized_target not in expected_allowed_files:
            errors.append(f"changes[{index}].file must be one of {sorted(expected_allowed_files)}")
        if self._is_protected_target(normalized_target):
            errors.append(f"changes[{index}].file must not target protected code, tests, or docs")
        if not normalized_target.endswith("/selectors.yaml"):
            errors.append(f"changes[{index}].file must target selectors.yaml")

        selector_id = change.get("selector_id")
        if selector_id not in expected_selector_refs:
            errors.append(f"changes[{index}].selector_id must be in {sorted(expected_selector_refs)}")

        field_name = change.get("field")
        if field_name not in {"primary", "fallbacks"}:
            errors.append(f"changes[{index}].field must be primary or fallbacks")
        elif field_name == "primary" and not isinstance(change.get("new"), str):
            errors.append(f"changes[{index}].new must be a string when field is primary")
        elif field_name == "fallbacks":
            new_value = change.get("new")
            if not isinstance(new_value, (str, list)):
                errors.append(f"changes[{index}].new must be a string or list when field is fallbacks")
            elif isinstance(new_value, list) and not all(isinstance(item, str) for item in new_value):
                errors.append(f"changes[{index}].new fallback entries must be strings")

    def _is_codex_style_patch(self, patch: dict[str, Any]) -> bool:
        return "changes" in patch or "scope" in patch or "failed_step_id" in patch

    def _is_protected_target(self, normalized_target: str) -> bool:
        parts = normalized_target.split("/")
        name = Path(normalized_target).name
        if name in self.PROTECTED_FILE_NAMES:
            return True
        if name.endswith(".py") or name.startswith("README") or name.startswith("requirements"):
            return True
        return any(segment in self.PROTECTED_PATH_SEGMENTS for segment in parts)

    def _read_json(self, path: str | Path) -> dict[str, Any]:
        with Path(path).open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"JSON root must be an object: {path}")
        return data
