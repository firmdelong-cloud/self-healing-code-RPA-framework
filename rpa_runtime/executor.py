"""Skill executor."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import uuid

from component_core import ComponentContext, ComponentRunner
from repair_agent.repair_request import RepairRequestGenerator
from rpa_runtime.logger import RunLogger
from rpa_runtime.observer import FailureSnapshot, Observer
from rpa_runtime.retry_policy import RetryPolicy
from rpa_runtime.selector_resolver import SelectorResolver
from rpa_runtime.step_runner import StepResult, StepRunner


@dataclass
class RunResult:
    run_id: str
    skill_id: str
    status: str
    steps: list[StepResult]
    outputs: dict[str, Any] | None = None
    failure_snapshot: FailureSnapshot | None = None
    repair_request_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        data["outputs"] = self.outputs or {}
        return data


class RPAExecutor:
    def __init__(
        self,
        *,
        storage_root: Path,
        browser: Any | None = None,
        confirmed_steps: set[str] | None = None,
    ):
        self.storage_root = storage_root
        self.browser = browser
        self.confirmed_steps = confirmed_steps or set()

    def run(self, skill: Any, *, page: Any | None = None) -> RunResult:
        run_id = str(uuid.uuid4())
        logger = RunLogger(run_id, self.storage_root / "runs")
        observer = Observer(self.storage_root / "snapshots")
        repair_generator = RepairRequestGenerator(self.storage_root / "repair_requests")

        own_session = None
        if page is None:
            if not self.browser:
                raise ValueError("A page or browser wrapper is required")
            own_session = self.browser.start()
            page = own_session.page

        retry_policy = RetryPolicy.from_dict(skill.repair_policy.get("retry", {}))
        runner = StepRunner(SelectorResolver(skill.selectors), retry_policy)
        results: list[StepResult] = []
        outputs: dict[str, Any] = {}
        logger.write("run_started", {"skill_id": skill.id, "skill_version": skill.version})

        try:
            if getattr(skill, "nodes", None):
                return self._run_component_workflow(
                    skill=skill,
                    page=page,
                    run_id=run_id,
                    logger=logger,
                    observer=observer,
                    repair_generator=repair_generator,
                    results=results,
                    outputs=outputs,
                )

            for step in skill.steps:
                logger.write("step_started", {"step": step})
                result = runner.run(
                    page,
                    step,
                    confirmed=step["id"] in self.confirmed_steps,
                    outputs=outputs,
                    storage_root=self.storage_root,
                    run_id=run_id,
                )
                results.append(result)
                logger.write("step_finished", result.to_dict())

                if result.status == "failed":
                    error = RuntimeError(result.error or "step failed")
                    snapshot = observer.capture_failure(
                        run_id=run_id,
                        step=step,
                        page=page,
                        error=error,
                        attempted_selectors=result.attempted_selectors,
                    )
                    repair_request_path = repair_generator.generate(
                        skill=skill,
                        run_id=run_id,
                        failed_step=step,
                        step_result=result,
                        snapshot=snapshot,
                    )
                    logger.write(
                        "run_failed",
                        {
                            "failed_step_id": step["id"],
                            "snapshot": Observer.to_dict(snapshot),
                            "repair_request_path": repair_request_path,
                        },
                    )
                    return RunResult(
                        run_id=run_id,
                        skill_id=skill.id,
                        status="failed",
                        steps=results,
                        outputs=outputs,
                        failure_snapshot=snapshot,
                        repair_request_path=repair_request_path,
                    )

            logger.write("run_succeeded", {"step_count": len(results), "outputs": outputs})
            return RunResult(run_id=run_id, skill_id=skill.id, status="success", steps=results, outputs=outputs)
        finally:
            if own_session:
                own_session.close()

    def _run_component_workflow(
        self,
        *,
        skill: Any,
        page: Any,
        run_id: str,
        logger: RunLogger,
        observer: Observer,
        repair_generator: RepairRequestGenerator,
        results: list[StepResult],
        outputs: dict[str, Any],
    ) -> RunResult:
        component_runner = ComponentRunner()
        context = ComponentContext(
            skill=skill,
            run_id=run_id,
            storage_root=self.storage_root,
            page=page,
            variables=dict(getattr(skill, "variables", {}) or {}),
            outputs=outputs,
            selector_resolver=SelectorResolver(skill.selectors),
            logger=logger,
        )

        for node in component_runner.ordered_nodes(skill.nodes, skill.edges):
            logger.write("node_started", {"node": node})
            result = component_runner.run_node(context, node)
            results.append(result)
            logger.write("node_finished", result.to_dict())

            if result.status == "failed":
                failed_node = self._node_for_repair(node)
                error = RuntimeError(result.error or "component failed")
                snapshot = observer.capture_failure(
                    run_id=run_id,
                    step=failed_node,
                    page=page,
                    error=error,
                    attempted_selectors=result.attempted_selectors or [],
                )
                repair_request_path = repair_generator.generate(
                    skill=skill,
                    run_id=run_id,
                    failed_step=failed_node,
                    step_result=result,
                    snapshot=snapshot,
                )
                logger.write(
                    "run_failed",
                    {
                        "failed_component_node_id": node["id"],
                        "failed_step_id": node["id"],
                        "snapshot": Observer.to_dict(snapshot),
                        "repair_request_path": repair_request_path,
                    },
                )
                return RunResult(
                    run_id=run_id,
                    skill_id=skill.id,
                    status="failed",
                    steps=results,
                    outputs=outputs,
                    failure_snapshot=snapshot,
                    repair_request_path=repair_request_path,
                )

        logger.write("run_succeeded", {"node_count": len(results), "outputs": outputs})
        return RunResult(run_id=run_id, skill_id=skill.id, status="success", steps=results, outputs=outputs)

    def _node_for_repair(self, node: dict[str, Any]) -> dict[str, Any]:
        inputs = node.get("inputs", {}) or {}
        repair_node = {
            "id": node.get("id"),
            "type": node.get("component", node.get("type")),
            "component": node.get("component", node.get("type")),
            "goal": node.get("goal", ""),
            "inputs": inputs,
            "target_description": node.get("target_description"),
        }
        if isinstance(inputs, dict) and inputs.get("selector_ref"):
            repair_node["selector_ref"] = inputs["selector_ref"]
        if node.get("requires_human_confirmation"):
            repair_node["requires_human_confirmation"] = node["requires_human_confirmation"]
        if node.get("risk_level"):
            repair_node["risk_level"] = node["risk_level"]
        return repair_node
