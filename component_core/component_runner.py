"""Component execution and built-in component definitions."""

from __future__ import annotations

import base64
import csv
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import unquote_to_bytes

from rpa_runtime.step_runner import StepResult

from .component_context import ComponentContext
from .component_registry import ComponentRegistry
from .component_schema import ComponentDefinition, ComponentRunResult


@dataclass(frozen=True)
class ComponentExecutionPlan:
    """Ordered component nodes for a Skill run."""

    nodes: list[dict[str, Any]]


class ComponentRunner:
    """Execute one component node at a time."""

    def __init__(self, registry: ComponentRegistry | None = None):
        self.registry = registry or default_component_registry()

    def ordered_nodes(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not edges:
            return list(nodes)

        node_by_id = {node["id"]: node for node in nodes}
        incoming = {node_id: 0 for node_id in node_by_id}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
        for edge in edges:
            source = str(edge.get("from"))
            target = str(edge.get("to"))
            if source in outgoing and target in incoming:
                outgoing[source].append(target)
                incoming[target] += 1

        queue = [node_id for node_id, count in incoming.items() if count == 0]
        ordered: list[dict[str, Any]] = []
        while queue:
            node_id = queue.pop(0)
            ordered.append(node_by_id[node_id])
            for target in outgoing[node_id]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)

        if len(ordered) != len(nodes):
            return list(nodes)
        return ordered

    def run_node(self, context: ComponentContext, node: dict[str, Any]) -> StepResult:
        started = perf_counter()
        node_id = str(node["id"])
        component_id = str(node.get("component") or node.get("type"))
        goal = str(node.get("goal", ""))
        rendered_inputs = context.render(node.get("inputs", {}) or {})

        try:
            component = self.registry.get(component_id)
            context.log(
                "component_started",
                {
                    "node_id": node_id,
                    "component_id": component_id,
                    "inputs": rendered_inputs,
                },
            )
            component_result = component.run(context, rendered_inputs)
            context.outputs.update(component_result.outputs)
            result = StepResult(
                step_id=node_id,
                step_type=component_id,
                goal=goal,
                status="success",
                duration=perf_counter() - started,
                selector_used=component_result.selector_used,
                selector_source=component_result.selector_source,
                attempted_selectors=component_result.attempted_selectors,
                outputs=component_result.outputs,
                inputs=rendered_inputs,
                component_id=component_id,
                node_id=node_id,
            )
            context.log("component_finished", result.to_dict())
            return result
        except Exception as error:
            result = StepResult(
                step_id=node_id,
                step_type=component_id,
                goal=goal,
                status="failed",
                duration=perf_counter() - started,
                error=str(error),
                attempted_selectors=list(context.last_attempted_selectors),
                inputs=rendered_inputs,
                component_id=component_id,
                node_id=node_id,
            )
            context.log("component_finished", result.to_dict())
            return result


def default_component_registry() -> ComponentRegistry:
    registry = ComponentRegistry()
    for component in _builtin_components():
        registry.register(component)
    return registry


def _component(
    *,
    component_id: str,
    name: str,
    category: str,
    description: str,
    run: Any,
    inputs_schema: dict[str, Any] | None = None,
    outputs_schema: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    repairable: bool = False,
    repair_scope: str = "none",
    risk_level: str = "low",
) -> ComponentDefinition:
    return ComponentDefinition(
        id=component_id,
        name=name,
        category=category,
        description=description,
        inputs_schema=inputs_schema or {},
        outputs_schema=outputs_schema or {},
        errors=errors or [],
        repairable=repairable,
        repair_scope=repair_scope,
        risk_level=risk_level,
        run=run,
    )


def _builtin_components() -> list[ComponentDefinition]:
    return [
        _component(
            component_id="browser.goto",
            name="Browser Go To",
            category="browser",
            description="Navigate the browser to a URL.",
            inputs_schema={"url": "string"},
            run=_browser_goto,
            errors=["NavigationError"],
        ),
        _component(
            component_id="browser.click",
            name="Browser Click",
            category="browser",
            description="Click a browser element through selector resolution.",
            inputs_schema={"selector_ref": "string"},
            run=_browser_click,
            errors=["SelectorResolutionError"],
            repairable=True,
            repair_scope="selector_only",
            risk_level="medium",
        ),
        _component(
            component_id="browser.fill",
            name="Browser Fill",
            category="browser",
            description="Fill a browser input through selector resolution.",
            inputs_schema={"selector_ref": "string", "value": "string"},
            run=_browser_fill,
            errors=["SelectorResolutionError"],
            repairable=True,
            repair_scope="selector_only",
            risk_level="medium",
        ),
        _component(
            component_id="browser.wait_for_selector",
            name="Browser Wait For Selector",
            category="browser",
            description="Wait for a browser selector through selector resolution.",
            inputs_schema={"selector_ref": "string"},
            run=_browser_wait_for_selector,
            errors=["SelectorResolutionError", "TimeoutError"],
            repairable=True,
            repair_scope="selector_only",
        ),
        _component(
            component_id="browser.extract_text",
            name="Browser Extract Text",
            category="browser",
            description="Extract text from a browser element.",
            inputs_schema={"selector_ref": "string"},
            outputs_schema={"text": "string"},
            run=_browser_extract_text,
            errors=["SelectorResolutionError"],
            repairable=True,
            repair_scope="selector_only",
        ),
        _component(
            component_id="file.exists",
            name="File Exists",
            category="file",
            description="Check whether a file exists.",
            inputs_schema={"path": "string"},
            outputs_schema={"exists": "boolean"},
            run=_file_exists,
            errors=["FileNotFoundError"],
        ),
        _component(
            component_id="file.write_text",
            name="File Write Text",
            category="file",
            description="Write UTF-8 text to a file.",
            inputs_schema={"path": "string", "text": "string"},
            outputs_schema={"path": "string"},
            run=_file_write_text,
        ),
        _component(
            component_id="excel.read",
            name="Excel Read",
            category="excel",
            description="Read CSV-compatible tabular data.",
            inputs_schema={"path": "string"},
            outputs_schema={"rows": "array"},
            run=_excel_read,
        ),
        _component(
            component_id="excel.write",
            name="Excel Write",
            category="excel",
            description="Write CSV-compatible tabular data.",
            inputs_schema={"path": "string", "rows": "array"},
            outputs_schema={"path": "string"},
            run=_excel_write,
        ),
        _component(
            component_id="control.if",
            name="Control If",
            category="control",
            description="Evaluate a boolean condition for downstream routing.",
            inputs_schema={"condition": "boolean"},
            outputs_schema={"condition_result": "boolean"},
            run=_control_if,
        ),
        _component(
            component_id="control.loop",
            name="Control Loop",
            category="control",
            description="Expose loop metadata for a list of items.",
            inputs_schema={"items": "array"},
            outputs_schema={"item_count": "integer"},
            run=_control_loop,
        ),
        _component(
            component_id="ai.generate_text",
            name="AI Generate Text",
            category="ai",
            description="Mock text generation for deterministic tests.",
            inputs_schema={"prompt": "string"},
            outputs_schema={"text": "string"},
            run=_ai_generate_text,
        ),
        _component(
            component_id="human.approval",
            name="Human Approval",
            category="human",
            description="Mock human approval gate.",
            inputs_schema={"approved": "boolean"},
            outputs_schema={"approved": "boolean"},
            run=_human_approval,
            risk_level="high",
        ),
        _component(
            component_id="system.log",
            name="System Log",
            category="system",
            description="Write a structured runtime log event.",
            inputs_schema={"message": "string"},
            run=_system_log,
        ),
    ]


def _browser_goto(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    context.page.goto(str(inputs["url"]))
    return ComponentRunResult()


def _browser_click(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    selector_ref = str(inputs["selector_ref"])
    selector, source, _, attempted = context.with_selector_ref(selector_ref, context.page.click)
    return ComponentRunResult(selector_used=selector, selector_source=source, attempted_selectors=attempted)


def _browser_fill(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    selector_ref = str(inputs["selector_ref"])
    value = str(inputs.get("value", ""))
    selector, source, _, attempted = context.with_selector_ref(
        selector_ref,
        lambda selector: context.page.fill(selector, value),
    )
    return ComponentRunResult(selector_used=selector, selector_source=source, attempted_selectors=attempted)


def _browser_wait_for_selector(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    selector_ref = str(inputs["selector_ref"])
    timeout = inputs.get("timeout_ms")

    def wait(selector: str) -> Any:
        if timeout is None:
            return context.page.wait_for_selector(selector)
        return context.page.wait_for_selector(selector, timeout=int(timeout))

    selector, source, _, attempted = context.with_selector_ref(selector_ref, wait)
    return ComponentRunResult(selector_used=selector, selector_source=source, attempted_selectors=attempted)


def _browser_extract_text(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    selector_ref = str(inputs["selector_ref"])
    attribute = inputs.get("attribute")
    selector, source, text, attempted = context.with_selector_ref(
        selector_ref,
        lambda selector: _read_selector_value(context.page, selector, attribute=attribute),
    )
    output_key = str(inputs.get("output_key", "text"))
    return ComponentRunResult(
        outputs={output_key: text},
        selector_used=selector,
        selector_source=source,
        attempted_selectors=attempted,
    )


def _file_exists(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    raw_path = inputs.get("path")
    if inputs.get("path_from_output"):
        raw_path = context.outputs.get(str(inputs["path_from_output"]))
    path = _resolve_existing_or_output_path(context, raw_path)
    exists = path.exists()
    if inputs.get("must_exist", False) and not exists:
        raise FileNotFoundError(str(path))
    output_key = str(inputs.get("output_key", "exists"))
    return ComponentRunResult(outputs={output_key: exists})


def _file_write_text(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    path = context.output_path(inputs["path"])
    path.write_text(str(inputs.get("text", "")), encoding="utf-8")
    return ComponentRunResult(outputs={str(inputs.get("output_key", "path")): str(path)})


def _excel_read(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    path = _resolve_existing_or_output_path(context, inputs["path"])
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = [row for row in csv.reader(file)]
    outputs: dict[str, Any] = {str(inputs.get("output_key", "rows")): rows}
    if inputs.get("row_count_output_key"):
        count = len(rows)
        if inputs.get("has_header", True) and count:
            count -= 1
        outputs[str(inputs["row_count_output_key"])] = count
    return ComponentRunResult(outputs=outputs)


def _excel_write(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    path = context.output_path(inputs["path"])
    rows = inputs.get("rows", [])
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow(list(row.values()))
            elif isinstance(row, list):
                writer.writerow(row)
            else:
                writer.writerow([row])
    return ComponentRunResult(outputs={str(inputs.get("output_key", "path")): str(path)})


def _control_if(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    value = inputs.get("condition", False)
    if isinstance(value, str):
        value = value.lower() in {"1", "true", "yes", "ok"}
    return ComponentRunResult(outputs={str(inputs.get("output_key", "condition_result")): bool(value)})


def _control_loop(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    items = inputs.get("items", [])
    if not isinstance(items, list):
        items = []
    return ComponentRunResult(outputs={str(inputs.get("output_key", "item_count")): len(items)})


def _ai_generate_text(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    data = inputs.get("data")
    if data is None and inputs.get("data_from_output"):
        data = context.outputs.get(str(inputs["data_from_output"]))
    if isinstance(data, list):
        generated = f"Mock AI summary: processed {max(len(data) - 1, 0)} data rows."
    else:
        generated = f"Mock AI summary: {str(inputs.get('prompt', 'No prompt provided.'))}"
    return ComponentRunResult(outputs={str(inputs.get("output_key", "generated_text")): generated})


def _human_approval(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    approved = bool(inputs.get("approved", True))
    if inputs.get("required", False) and not approved:
        raise PermissionError("human approval rejected")
    return ComponentRunResult(outputs={str(inputs.get("output_key", "approved")): approved})


def _system_log(context: ComponentContext, inputs: dict[str, Any]) -> ComponentRunResult:
    payload = dict(inputs.get("payload", {}) or {})
    message = str(inputs.get("message", ""))
    context.log("system_log", {"message": message, "payload": payload})
    return ComponentRunResult(outputs={str(inputs.get("output_key", "logged")): True})


def _text_content(page: Any, selector: str) -> str:
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


def _read_selector_value(page: Any, selector: str, *, attribute: Any = None) -> str:
    if attribute:
        if not hasattr(page, "get_attribute"):
            raise RuntimeError("page does not support attribute extraction")
        value = page.get_attribute(selector, str(attribute))
        if value is None:
            raise RuntimeError(f"selector has no attribute '{attribute}': {selector}")
        value = str(value)
        if value.startswith("data:"):
            return _decode_data_url(value)
        return value
    return _text_content(page, selector)


def _decode_data_url(href: str) -> str:
    header, _, payload = href.partition(",")
    if ";base64" in header:
        data = base64.b64decode(payload)
    else:
        data = unquote_to_bytes(payload)
    return data.decode("utf-8", errors="replace")


def _resolve_existing_or_output_path(context: ComponentContext, raw_path: Any) -> Path:
    rendered = context.render(raw_path)
    path = Path(str(rendered))
    if path.is_absolute():
        return path
    output_path = context.storage_root / "outputs" / context.run_id / path
    if output_path.exists():
        return output_path
    return path
