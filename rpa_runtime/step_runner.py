"""Single-step execution with logging and deterministic selector fallback."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Any

from rpa_runtime.exceptions import HumanConfirmationRequired, SelectorNotFoundError
from rpa_runtime.retry_policy import RetryPolicy
from rpa_runtime.selector_resolver import SelectorResolver


@dataclass
class StepResult:
    step_id: str
    goal: str
    status: str
    duration: float
    error: str | None = None
    selector_used: str | None = None
    selector_source: str | None = None
    attempted_selectors: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StepRunner:
    def __init__(self, selector_resolver: SelectorResolver, retry_policy: RetryPolicy | None = None):
        self.selector_resolver = selector_resolver
        self.retry_policy = retry_policy or RetryPolicy()

    def run(self, page: Any, step: dict[str, Any], *, confirmed: bool = False) -> StepResult:
        started = perf_counter()
        step_id = step["id"]
        goal = step.get("goal", "")
        attempted_selectors: list[str] = []

        try:
            if step.get("requires_human_confirmation") and not confirmed:
                reason = step.get("risk_reason", "high-risk operation")
                raise HumanConfirmationRequired(f"Step '{step_id}' requires human confirmation: {reason}")

            selector_used, selector_source = self._run_with_retry(page, step, attempted_selectors)
            return StepResult(
                step_id=step_id,
                goal=goal,
                status="success",
                duration=perf_counter() - started,
                selector_used=selector_used,
                selector_source=selector_source,
                attempted_selectors=attempted_selectors,
            )
        except Exception as error:
            return StepResult(
                step_id=step_id,
                goal=goal,
                status="failed",
                duration=perf_counter() - started,
                error=str(error),
                attempted_selectors=attempted_selectors,
            )

    def _run_with_retry(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[str | None, str | None]:
        last_error: Exception | None = None
        for attempt_index in range(self.retry_policy.max_attempts):
            self.retry_policy.wait_before_retry(attempt_index)
            try:
                return self._execute(page, step, attempted_selectors)
            except Exception as error:
                last_error = error
        if last_error:
            raise last_error
        return None, None

    def _execute(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[str | None, str | None]:
        step_type = step["type"]
        if step_type == "navigate":
            page.goto(step["url"])
            return None, None
        if step_type == "click":
            return self._with_selector(page.click, step, attempted_selectors)
        if step_type == "fill":
            value = step.get("value", "")
            return self._with_selector(lambda selector: page.fill(selector, value), step, attempted_selectors)
        if step_type == "login":
            return self._login(page, step, attempted_selectors)
        if step_type == "select_date_range":
            return self._select_date_range(page, step, attempted_selectors)
        if step_type == "wait_for_selector":
            return self._with_selector(page.wait_for_selector, step, attempted_selectors)
        raise ValueError(f"Unsupported step type: {step_type}")

    def _with_selector(
        self,
        action: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[str, str]:
        selector_ref = step["selector_ref"]
        return self._with_selector_ref(action, selector_ref, attempted_selectors)

    def _with_selector_ref(
        self,
        action: Any,
        selector_ref: str,
        attempted_selectors: list[str],
    ) -> tuple[str, str]:
        candidates = self.selector_resolver.candidates_for(selector_ref)
        last_error = ""
        for candidate in candidates:
            attempted_selectors.append(candidate.selector)
            try:
                action(candidate.selector)
                return candidate.selector, candidate.source
            except Exception as error:
                last_error = str(error)
        raise SelectorNotFoundError(selector_ref, attempted_selectors, last_error)

    def _login(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[str, str]:
        selector_refs = step["selector_refs"]
        self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("username_value", "")),
            selector_refs["username"],
            attempted_selectors,
        )
        self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("password_value", "")),
            selector_refs["password"],
            attempted_selectors,
        )
        return self._with_selector_ref(page.click, selector_refs["submit"], attempted_selectors)

    def _select_date_range(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[str, str]:
        selector_refs = step["selector_refs"]
        self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("start_date", "")),
            selector_refs["start_date"],
            attempted_selectors,
        )
        return self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("end_date", "")),
            selector_refs["end_date"],
            attempted_selectors,
        )
