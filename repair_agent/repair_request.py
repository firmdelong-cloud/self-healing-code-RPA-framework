"""Generate safe, narrow repair requests for failed steps."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


class RepairRequestGenerator:
    """Create repair_request.json without calling an LLM."""

    SENSITIVE_KEY_PATTERN = re.compile(
        r"(password|passwd|secret|token|api[_-]?key|cookie|session|authorization)",
        re.IGNORECASE,
    )

    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        *,
        skill: Any,
        run_id: str,
        failed_step: dict[str, Any],
        step_result: Any,
        snapshot: Any,
    ) -> str:
        request_dir = self.output_root / run_id
        request_dir.mkdir(parents=True, exist_ok=True)
        path = request_dir / "repair_request.json"

        selector_ref = failed_step.get("selector_ref")
        selector_entry = skill.selectors.get(selector_ref, {}) if selector_ref else {}

        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "skill_id": skill.id,
            "skill_name": skill.name,
            "skill_version": skill.version,
            "failed_step_id": failed_step.get("id"),
            "failed_step_goal": failed_step.get("goal"),
            "error_type": self._error_type(step_result.error),
            "error_message": step_result.error,
            "current_url": snapshot.current_url,
            "screenshot_path": snapshot.screenshot_path,
            "dom_snapshot_path": snapshot.dom_path,
            "original_code_snippet": self._original_code_snippet(failed_step),
            "original_selector": selector_entry.get("primary"),
            "fallback_selectors": selector_entry.get("fallbacks", []),
            "recent_success_snapshot_path": self._recent_success_snapshot_path(skill, failed_step),
            "allowed_repair_scope": self._allowed_repair_scope(skill, failed_step, selector_ref),
            "forbidden_actions": self._forbidden_actions(),
            "human_approval_required": bool(failed_step.get("requires_human_confirmation", False)),
            "test_command": self._test_command(skill),
            "rollback_version": skill.version,
            "risk_level": self._risk_level(failed_step),
        }

        safe_payload = self._redact(payload)
        path.write_text(json.dumps(safe_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _allowed_files(self, skill: Any) -> list[str]:
        return [
            self._relative_to_project_root(skill, skill.selectors_path),
        ]

    def _allowed_repair_scope(self, skill: Any, failed_step: dict[str, Any], selector_ref: str | None) -> dict[str, Any]:
        return {
            "scope_type": "selector_only",
            "failed_step_id": failed_step.get("id"),
            "allowed_files": self._allowed_files(skill),
            "allowed_selector_refs": [selector_ref] if selector_ref else [],
            "must_not_touch_other_steps": True,
            "must_not_touch_runtime": True,
        }

    def _error_type(self, error_message: str | None) -> str:
        if not error_message:
            return "UnknownError"
        if "Selector" in error_message or "selector not found" in error_message:
            return "SelectorResolutionError"
        if "Timeout" in error_message or "timeout" in error_message:
            return "TimeoutError"
        if "human confirmation" in error_message:
            return "HumanConfirmationRequired"
        return "StepExecutionError"

    def _forbidden_actions(self) -> list[str]:
        return [
            "rewrite_entire_skill",
            "modify_unrelated_steps",
            "remove_or_weaken_human_approval",
            "bypass_permission_or_auth_checks",
            "disable_logging",
            "disable_snapshot_capture",
            "delete_or_skip_tests",
            "hardcode_credentials_or_tokens",
            "increase_action_scope",
        ]

    def _original_code_snippet(self, failed_step: dict[str, Any]) -> str:
        safe_step = self._redact(failed_step)
        return json.dumps(safe_step, indent=2, ensure_ascii=False)

    def _recent_success_snapshot_path(self, skill: Any, failed_step: dict[str, Any]) -> str | None:
        return failed_step.get("recent_success_snapshot_path") or getattr(skill, "recent_success_snapshot_path", None)

    def _risk_level(self, failed_step: dict[str, Any]) -> str:
        if failed_step.get("risk_level"):
            return str(failed_step["risk_level"])
        if failed_step.get("requires_human_confirmation"):
            return "high"
        step_type = str(failed_step.get("type", "")).lower()
        step_id = str(failed_step.get("id", "")).lower()
        goal = str(failed_step.get("goal", "")).lower()
        risky_words = ("delete", "payment", "pay", "approve", "submit", "publish", "permission")
        if any(word in step_id or word in goal for word in risky_words):
            return "high"
        if step_type in {"click", "fill", "login", "select_date_range"}:
            return "medium"
        return "low"

    def _test_command(self, skill: Any) -> list[str]:
        command = skill.repair_policy.get("sandbox", {}).get("command")
        if isinstance(command, list) and command:
            return [str(item) for item in command]
        return ["python", "-m", "pytest"]

    def _relative_to_project_root(self, skill: Any, path: Path) -> str:
        project_root = self._infer_project_root(skill)
        return path.resolve().relative_to(project_root).as_posix()

    def _infer_project_root(self, skill: Any) -> Path:
        base_path = skill.base_path.resolve()
        for parent in [base_path, *base_path.parents]:
            if (parent / "rpa_runtime").exists() and (parent / "skill_registry").exists():
                return parent
        return base_path.parent

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if self.SENSITIVE_KEY_PATTERN.search(str(key)):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(item)
            return redacted
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            return self._redact_string(value)
        return value

    def _redact_string(self, value: str) -> str:
        value = re.sub(
            r"(?i)(password|passwd|secret|token|api[_-]?key|session|authorization)=([^&\s]+)",
            r"\1=[REDACTED]",
            value,
        )
        value = re.sub(
            r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+",
            r"\1[REDACTED]",
            value,
        )
        return value
