"""Skill executor."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import uuid

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
    failure_snapshot: FailureSnapshot | None = None
    repair_request_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
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
        logger.write("run_started", {"skill_id": skill.id, "skill_version": skill.version})

        try:
            for step in skill.steps:
                logger.write("step_started", {"step": step})
                result = runner.run(page, step, confirmed=step["id"] in self.confirmed_steps)
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
                        failure_snapshot=snapshot,
                        repair_request_path=repair_request_path,
                    )

            logger.write("run_succeeded", {"step_count": len(results)})
            return RunResult(run_id=run_id, skill_id=skill.id, status="success", steps=results)
        finally:
            if own_session:
                own_session.close()

