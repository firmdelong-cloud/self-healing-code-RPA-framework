"""Single-step execution with deterministic selector fallback and outputs."""

from __future__ import annotations

import base64
import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from time import perf_counter
from typing import Any
from urllib.parse import unquote_to_bytes

from rpa_runtime.exceptions import HumanConfirmationRequired, SelectorNotFoundError
from rpa_runtime.retry_policy import RetryPolicy
from rpa_runtime.selector_resolver import SelectorResolver


@dataclass
class StepResult:
    step_id: str
    step_type: str
    goal: str
    status: str
    duration: float
    error: str | None = None
    selector_used: str | None = None
    selector_source: str | None = None
    attempted_selectors: list[str] | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    component_id: str | None = None
    node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StepExecution:
    selector_used: str | None = None
    selector_source: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)


class StepRunner:
    TABLE_EXTRACTION_JS = """
    table => Array.from(table.querySelectorAll("tr"))
      .map(row => Array.from(row.querySelectorAll("th, td"))
      .map(cell => cell.innerText.trim()))
      .filter(row => row.length > 0)
    """

    def __init__(self, selector_resolver: SelectorResolver, retry_policy: RetryPolicy | None = None):
        self.selector_resolver = selector_resolver
        self.retry_policy = retry_policy or RetryPolicy()

    def run(
        self,
        page: Any,
        step: dict[str, Any],
        *,
        confirmed: bool = False,
        outputs: dict[str, Any] | None = None,
        storage_root: Path | None = None,
        run_id: str | None = None,
    ) -> StepResult:
        started = perf_counter()
        step_id = step["id"]
        step_type = step["type"]
        goal = step.get("goal", "")
        attempted_selectors: list[str] = []
        run_outputs = outputs if outputs is not None else {}

        try:
            if step.get("requires_human_confirmation") and not confirmed:
                reason = step.get("risk_reason", "high-risk operation")
                raise HumanConfirmationRequired(f"Step '{step_id}' requires human confirmation: {reason}")

            execution = self._run_with_retry(
                page,
                step,
                attempted_selectors,
                run_outputs=run_outputs,
                storage_root=storage_root,
                run_id=run_id,
            )
            run_outputs.update(execution.outputs)
            return StepResult(
                step_id=step_id,
                step_type=step_type,
                goal=goal,
                status="success",
                duration=perf_counter() - started,
                selector_used=execution.selector_used,
                selector_source=execution.selector_source,
                attempted_selectors=attempted_selectors,
                outputs=execution.outputs,
            )
        except Exception as error:
            return StepResult(
                step_id=step_id,
                step_type=step_type,
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
        *,
        run_outputs: dict[str, Any],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        last_error: Exception | None = None
        for attempt_index in range(self.retry_policy.max_attempts):
            self.retry_policy.wait_before_retry(attempt_index)
            try:
                return self._execute(
                    page,
                    step,
                    attempted_selectors,
                    run_outputs=run_outputs,
                    storage_root=storage_root,
                    run_id=run_id,
                )
            except Exception as error:
                last_error = error
        if last_error:
            raise last_error
        return StepExecution()

    def _execute(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
        *,
        run_outputs: dict[str, Any],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        step_type = step["type"]
        if step_type in {"goto", "navigate"}:
            page.goto(step["url"])
            return StepExecution()
        if step_type == "click":
            return self._selector_execution(page.click, step, attempted_selectors)
        if step_type == "fill":
            value = str(step.get("value", ""))
            return self._selector_execution(lambda selector: page.fill(selector, value), step, attempted_selectors)
        if step_type == "select":
            return self._select(page, step, attempted_selectors)
        if step_type in {"wait_for", "wait_for_selector"}:
            return self._wait_for(page, step, attempted_selectors)
        if step_type == "extract_text":
            return self._extract_text(page, step, attempted_selectors)
        if step_type == "extract_table":
            return self._extract_table_step(page, step, attempted_selectors, storage_root, run_id)
        if step_type == "download_file":
            return self._download_file(page, step, attempted_selectors, storage_root, run_id)
        if step_type == "assert_text":
            return self._assert_text(page, step, attempted_selectors)
        if step_type == "assert_url":
            return self._assert_url(page, step)
        if step_type == "screenshot":
            return self._screenshot(page, step, storage_root, run_id)
        if step_type == "assert_file_exists":
            return self._assert_file_exists(step, run_outputs, storage_root, run_id)
        if step_type == "login":
            return self._login(page, step, attempted_selectors)
        if step_type == "select_date_range":
            return self._select_date_range(page, step, attempted_selectors)
        raise ValueError(f"Unsupported step type: {step_type}")

    def _selector_execution(
        self,
        action: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        selector_ref = step["selector_ref"]
        selector, source, _ = self._with_selector_ref(action, selector_ref, attempted_selectors)
        return StepExecution(selector_used=selector, selector_source=source)

    def _with_selector_ref(
        self,
        action: Any,
        selector_ref: str,
        attempted_selectors: list[str],
    ) -> tuple[str, str, Any]:
        candidates = self.selector_resolver.candidates_for(selector_ref)
        last_error = ""
        for candidate in candidates:
            attempted_selectors.append(candidate.selector)
            try:
                action_result = action(candidate.selector)
                return candidate.selector, candidate.source, action_result
            except Exception as error:
                last_error = str(error)
        raise SelectorNotFoundError(selector_ref, attempted_selectors, last_error)

    def _select(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        value = step.get("value", "")

        def action(selector: str) -> None:
            if hasattr(page, "select_option"):
                page.select_option(selector, value)
                return
            page.fill(selector, str(value))

        return self._selector_execution(action, step, attempted_selectors)

    def _wait_for(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        timeout = step.get("timeout_ms")
        if step.get("selector_ref"):
            return self._selector_execution(
                lambda selector: self._wait_for_selector(page, selector, timeout),
                step,
                attempted_selectors,
            )
        if hasattr(page, "wait_for_timeout"):
            page.wait_for_timeout(int(timeout or 1000))
            return StepExecution()
        raise ValueError("wait_for requires selector_ref or a page with wait_for_timeout")

    def _wait_for_selector(self, page: Any, selector: str, timeout: Any = None) -> Any:
        if timeout is None:
            return page.wait_for_selector(selector)
        return page.wait_for_selector(selector, timeout=int(timeout))

    def _extract_text(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        selector_ref = step["selector_ref"]
        selector, source, text = self._with_selector_ref(
            lambda selector: self._text_content(page, selector),
            selector_ref,
            attempted_selectors,
        )
        key = step.get("output_key", step["id"])
        return StepExecution(selector_used=selector, selector_source=source, outputs={key: text})

    def _extract_table_step(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        selector_ref = step["selector_ref"]
        selector, source, rows = self._with_selector_ref(
            lambda selector: self._extract_table(page, selector),
            selector_ref,
            attempted_selectors,
        )
        normalized_rows = self._normalize_rows(rows)
        outputs: dict[str, Any] = {step.get("output_key", step["id"]): normalized_rows}

        row_count_key = step.get("row_count_output_key")
        if row_count_key:
            data_row_count = len(normalized_rows)
            if step.get("has_header", True) and data_row_count:
                data_row_count -= 1
            outputs[row_count_key] = data_row_count

        output_path = step.get("output_path") or step.get("csv_path")
        if output_path:
            csv_path = self._resolve_output_path(output_path, storage_root, run_id)
            self._write_csv(csv_path, normalized_rows)
            outputs[step.get("output_path_key", "csv_path")] = str(csv_path)

        return StepExecution(selector_used=selector, selector_source=source, outputs=outputs)

    def _download_file(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        target_path = self._resolve_output_path(
            step.get("output_path", step.get("filename", "download.bin")),
            storage_root,
            run_id,
        )
        selector_ref = step["selector_ref"]
        selector, source, downloaded_path = self._with_selector_ref(
            lambda selector: self._download_from_selector(page, selector, target_path, step),
            selector_ref,
            attempted_selectors,
        )
        return StepExecution(
            selector_used=selector,
            selector_source=source,
            outputs={step.get("output_key", "download_path"): str(downloaded_path)},
        )

    def _assert_text(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        expected = str(step.get("expected_text", step.get("contains", "")))
        if not expected:
            raise ValueError("assert_text requires expected_text or contains")

        if step.get("selector_ref"):
            selector_ref = step["selector_ref"]
            selector, source, actual = self._with_selector_ref(
                lambda selector: self._text_content(page, selector),
                selector_ref,
                attempted_selectors,
            )
            if expected not in actual:
                raise AssertionError(f"Expected text '{expected}' not found in selector '{selector}'")
            return StepExecution(selector_used=selector, selector_source=source)

        actual = page.content() if hasattr(page, "content") else ""
        if expected not in actual:
            raise AssertionError(f"Expected text '{expected}' not found in page")
        return StepExecution()

    def _assert_url(self, page: Any, step: dict[str, Any]) -> StepExecution:
        current_url = str(getattr(page, "url", ""))
        expected = step.get("expected_url")
        contains = step.get("url_contains")
        pattern = step.get("url_matches")

        if expected is not None and current_url != str(expected):
            raise AssertionError(f"Expected URL '{expected}', got '{current_url}'")
        if contains is not None and str(contains) not in current_url:
            raise AssertionError(f"Expected URL to contain '{contains}', got '{current_url}'")
        if pattern is not None and not re.search(str(pattern), current_url):
            raise AssertionError(f"Expected URL to match '{pattern}', got '{current_url}'")
        if expected is None and contains is None and pattern is None:
            raise ValueError("assert_url requires expected_url, url_contains, or url_matches")
        return StepExecution()

    def _screenshot(
        self,
        page: Any,
        step: dict[str, Any],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        path = self._resolve_output_path(step.get("output_path", f"{step['id']}.png"), storage_root, run_id)
        page.screenshot(path=str(path), full_page=bool(step.get("full_page", True)))
        return StepExecution(outputs={step.get("output_key", "screenshot_path"): str(path)})

    def _assert_file_exists(
        self,
        step: dict[str, Any],
        run_outputs: dict[str, Any],
        storage_root: Path | None,
        run_id: str | None,
    ) -> StepExecution:
        path_value = step.get("path")
        if step.get("path_from_output"):
            path_value = run_outputs.get(step["path_from_output"])
        if not path_value:
            raise ValueError("assert_file_exists requires path or path_from_output")

        path = Path(str(path_value))
        if not path.is_absolute():
            path = self._resolve_output_path(str(path), storage_root, run_id)
        if not path.exists():
            raise AssertionError(f"Expected file to exist: {path}")
        return StepExecution()

    def _login(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
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
        selector, source, _ = self._with_selector_ref(page.click, selector_refs["submit"], attempted_selectors)
        return StepExecution(selector_used=selector, selector_source=source)

    def _select_date_range(
        self,
        page: Any,
        step: dict[str, Any],
        attempted_selectors: list[str],
    ) -> StepExecution:
        selector_refs = step["selector_refs"]
        self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("start_date", "")),
            selector_refs["start_date"],
            attempted_selectors,
        )
        selector, source, _ = self._with_selector_ref(
            lambda selector: page.fill(selector, step.get("end_date", "")),
            selector_refs["end_date"],
            attempted_selectors,
        )
        return StepExecution(selector_used=selector, selector_source=source)

    def _text_content(self, page: Any, selector: str) -> str:
        if hasattr(page, "text_content"):
            text = page.text_content(selector)
            if text is None:
                raise RuntimeError(f"selector has no text: {selector}")
            return str(text)
        if hasattr(page, "inner_text"):
            return str(page.inner_text(selector))
        if hasattr(page, "locator"):
            return str(page.locator(selector).text_content())
        raise RuntimeError("page does not support text extraction")

    def _extract_table(self, page: Any, selector: str) -> list[list[str]]:
        if hasattr(page, "extract_table"):
            return page.extract_table(selector)
        if hasattr(page, "eval_on_selector"):
            rows = page.eval_on_selector(selector, self.TABLE_EXTRACTION_JS)
            return self._normalize_rows(rows)
        raise RuntimeError("page does not support table extraction")

    def _normalize_rows(self, rows: Any) -> list[list[str]]:
        if not isinstance(rows, list):
            raise RuntimeError("table extraction did not return rows")
        normalized: list[list[str]] = []
        for row in rows:
            if not isinstance(row, list):
                raise RuntimeError("table extraction rows must be lists")
            normalized.append([str(cell) for cell in row])
        return normalized

    def _download_from_selector(self, page: Any, selector: str, target_path: Path, step: dict[str, Any]) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        if hasattr(page, "expect_download"):
            try:
                with page.expect_download(timeout=int(step.get("timeout_ms", 5000))) as download_info:
                    page.click(selector)
                download = download_info.value
                download.save_as(str(target_path))
                return target_path
            except Exception as error:
                last_error = error

        href = None
        if hasattr(page, "get_attribute"):
            href = page.get_attribute(selector, "href")
        if isinstance(href, str) and href.startswith("data:"):
            target_path.write_bytes(self._decode_data_url(href))
            return target_path

        if "simulated_content" in step:
            if hasattr(page, "click"):
                page.click(selector)
            target_path.write_text(str(step["simulated_content"]), encoding="utf-8")
            return target_path

        if last_error:
            raise last_error
        raise RuntimeError("download_file requires a browser download, data href, or simulated_content")

    def _decode_data_url(self, href: str) -> bytes:
        header, _, payload = href.partition(",")
        if ";base64" in header:
            return base64.b64decode(payload)
        return unquote_to_bytes(payload)

    def _write_csv(self, path: Path, rows: list[list[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(rows)

    def _resolve_output_path(self, path_value: Any, storage_root: Path | None, run_id: str | None) -> Path:
        rendered = str(path_value).format(run_id=run_id or "")
        path = Path(rendered)
        if path.is_absolute():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        base = storage_root / "outputs" / (run_id or "manual") if storage_root else Path.cwd()
        resolved = base / path
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved
