"""Execution context shared by component nodes."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from rpa_runtime.selector_resolver import SelectorResolver


class ComponentContext:
    """Holds runtime state, page handles, outputs, and helper APIs."""

    PLACEHOLDER_RE = re.compile(r"^\{\{([A-Za-z0-9_.-]+)\}\}$")
    INLINE_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_.-]+)\}\}")

    def __init__(
        self,
        *,
        skill: Any,
        run_id: str,
        storage_root: Path,
        page: Any | None = None,
        variables: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        selector_resolver: SelectorResolver | None = None,
        logger: Any | None = None,
    ):
        self.skill = skill
        self.run_id = run_id
        self.storage_root = storage_root
        self.page = page
        self.variables = variables or {}
        self.outputs = outputs if outputs is not None else {}
        self.selector_resolver = selector_resolver or SelectorResolver(getattr(skill, "selectors", {}) or {})
        self.logger = logger
        self.last_attempted_selectors: list[str] = []

    def render(self, value: Any) -> Any:
        """Resolve placeholders from variables and previous component outputs."""

        if isinstance(value, dict):
            return {key: self.render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.render(item) for item in value]
        if not isinstance(value, str):
            return value

        exact = self.PLACEHOLDER_RE.match(value)
        if exact:
            return self.lookup(exact.group(1))

        def replace(match: re.Match[str]) -> str:
            resolved = self.lookup(match.group(1))
            return str(resolved)

        return self.INLINE_PLACEHOLDER_RE.sub(replace, value)

    def lookup(self, key: str) -> Any:
        if key == "run_id":
            return self.run_id
        if key.startswith("outputs."):
            return self.outputs.get(key.split(".", 1)[1], "")
        if key.startswith("variables."):
            return self.variables.get(key.split(".", 1)[1], "")
        if key in self.outputs:
            return self.outputs[key]
        if key in self.variables:
            return self.variables[key]
        if key in getattr(self.skill, "inputs", {}):
            input_config = self.skill.inputs[key]
            if isinstance(input_config, dict) and "default" in input_config:
                return input_config["default"]
            return input_config
        return f"{{{{{key}}}}}"

    def output_path(self, path_value: Any) -> Path:
        rendered = str(self.render(path_value)).format(run_id=self.run_id)
        path = Path(rendered)
        if path.is_absolute():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        resolved = self.storage_root / "outputs" / self.run_id / path
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def with_selector_ref(self, selector_ref: str, action: Any) -> tuple[str, str, Any, list[str]]:
        attempted: list[str] = []
        last_error = ""
        for candidate in self.selector_resolver.candidates_for(selector_ref):
            attempted.append(candidate.selector)
            self.last_attempted_selectors = list(attempted)
            try:
                result = action(candidate.selector)
                return candidate.selector, candidate.source, result, attempted
            except Exception as error:
                last_error = str(error)
        raise RuntimeError(last_error or f"selector not found: {selector_ref}")

    def log(self, event: str, payload: dict[str, Any] | None = None) -> None:
        if self.logger is not None:
            self.logger.write(event, payload or {})

    def write_json_log(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
