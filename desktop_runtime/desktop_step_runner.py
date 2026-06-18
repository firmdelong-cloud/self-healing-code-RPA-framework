"""Desktop message Skill executor and step runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
import uuid

from message_runtime import (
    AutoSendPolicy,
    ConversationLogger,
    IntentClassifier,
    MessageParser,
    ReplyEngine,
    SafetyGuard,
)
from rpa_runtime.logger import RunLogger
from rpa_runtime.selector_resolver import SelectorResolver
from rpa_runtime.step_runner import StepResult

from .app_finder import AppFinder
from .input_controller import fill_text as apply_fill_text, send_message as apply_send_message
from .screenshot_observer import DesktopFailureSnapshot, ScreenshotObserver
from .ui_reader import detect_unread, read_chat_text


@dataclass
class DesktopRunResult:
    run_id: str
    skill_id: str
    status: str
    steps: list[StepResult]
    outputs: dict[str, Any]
    failure_snapshot: DesktopFailureSnapshot | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() for step in self.steps]
        if self.failure_snapshot:
            payload["failure_snapshot"] = self.failure_snapshot.to_dict()
        return payload


class DesktopStepRunner:
    """Execute desktop-specific Skill steps against a window abstraction."""

    def __init__(self, *, skill: Any, storage_root: Path):
        self.skill = skill
        self.storage_root = storage_root
        self.selector_resolver = SelectorResolver(skill.selectors)
        self.parser = MessageParser()
        self.intent_classifier = IntentClassifier()
        self.reply_engine = ReplyEngine()
        self.safety_guard = SafetyGuard()
        self.policy_guard = AutoSendPolicy()
        self.conversation_logger = ConversationLogger(storage_root / "conversations", skill_id=skill.id)

    def run(self, window: Any, step: dict[str, Any], *, outputs: dict[str, Any]) -> StepResult:
        started = perf_counter()
        step_id = step["id"]
        step_type = step["type"]
        goal = step.get("goal", "")
        attempted_selectors: list[str] = []
        try:
            step_outputs, selector_used, selector_source = self._execute(window, step, outputs, attempted_selectors)
            outputs.update(step_outputs)
            return StepResult(
                step_id=step_id,
                step_type=step_type,
                goal=goal,
                status="success",
                duration=perf_counter() - started,
                selector_used=selector_used,
                selector_source=selector_source,
                attempted_selectors=attempted_selectors,
                outputs=step_outputs,
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

    def _execute(
        self,
        window: Any,
        step: dict[str, Any],
        outputs: dict[str, Any],
        attempted_selectors: list[str],
    ) -> tuple[dict[str, Any], str | None, str | None]:
        step_type = step["type"]
        if step_type == "open_window":
            window.open(step["url"])
            return {"window_runtime": self.skill.runtime}, None, None
        if step_type == "detect_unread":
            state, selector_used, selector_source = self._with_selector_ref(
                step["selector_ref"],
                attempted_selectors,
                lambda selector: detect_unread(window, selector),
            )
            return ({
                "contact_name": state["contact_name"],
                "unread_count": state["unread_count"],
                "is_group_chat": state.get("is_group_chat", False),
            }, selector_used, selector_source)
        if step_type == "click_chat":
            state, selector_used, selector_source = self._with_selector_ref(
                step["selector_ref"],
                attempted_selectors,
                lambda selector: window.click_chat(selector),
            )
            return ({
                "contact_name": state["contact_name"],
                "is_group_chat": state.get("is_group_chat", False),
            }, selector_used, selector_source)
        if step_type == "read_chat_text":
            latest_message, selector_used, selector_source = self._with_selector_ref(
                step["selector_ref"],
                attempted_selectors,
                lambda selector: read_chat_text(window, selector),
            )
            parsed = self.parser.parse(
                contact_name=str(outputs.get("contact_name", "")),
                latest_message=latest_message,
                is_group_chat=bool(outputs.get("is_group_chat", False)),
            )
            self.conversation_logger.record(
                "message_received",
                contact_name=parsed.contact_name,
                payload={"latest_message": parsed.latest_message, "is_group_chat": parsed.is_group_chat},
            )
            return parsed.to_dict(), selector_used, selector_source
        if step_type == "classify_intent":
            message = str(outputs.get(step.get("message_key", "normalized_text"), outputs.get("latest_message", "")))
            intent_result = self.intent_classifier.classify(message)
            return intent_result.to_dict(), None, None
        if step_type == "generate_reply":
            reply_result = self.reply_engine.generate(
                intent=str(outputs.get("intent", "general_inquiry")),
                latest_message=str(outputs.get("latest_message", "")),
                contact_name=str(outputs.get("contact_name", "")),
            )
            return reply_result.to_dict(), None, None
        if step_type == "safety_check":
            decision = self.safety_guard.evaluate(
                intent=str(outputs.get("intent", "")),
                latest_message=str(outputs.get("latest_message", "")),
                policy=self.skill.policy,
            )
            return ({
                "safety_allowed": decision.allowed,
                "handoff_required": decision.handoff_required,
                "risk_level": decision.risk_level,
                "safety_reasons": decision.reasons,
            }, None, None)
        if step_type == "auto_send_policy":
            from message_runtime.safety_guard import SafetyDecision

            safety_decision = SafetyDecision(
                allowed=bool(outputs.get("safety_allowed", False)),
                handoff_required=bool(outputs.get("handoff_required", False)),
                reasons=list(outputs.get("safety_reasons", [])),
                risk_level=str(outputs.get("risk_level", "low")),
            )
            decision = self.policy_guard.evaluate(
                contact_name=str(outputs.get("contact_name", "")),
                is_group_chat=bool(outputs.get("is_group_chat", False)),
                policy=self.skill.policy,
                logger=self.conversation_logger,
                safety_decision=safety_decision,
            )
            return ({
                "auto_send_allowed": decision.allowed,
                "handoff_required": decision.handoff_required or bool(outputs.get("handoff_required", False)),
                "policy_reasons": decision.reasons,
            }, None, None)
        if step_type == "fill_text":
            reply_text = str(outputs.get(step.get("reply_output_key", "reply_text"), ""))
            _, selector_used, selector_source = self._with_selector_ref(
                step["selector_ref"],
                attempted_selectors,
                lambda selector: apply_fill_text(window, selector, reply_text),
            )
            return {"reply_text": reply_text, "draft_filled": True}, selector_used, selector_source
        if step_type == "send_message":
            if not bool(outputs.get("auto_send_allowed", False)):
                self.conversation_logger.record(
                    "message_blocked",
                    contact_name=str(outputs.get("contact_name", "")),
                    payload={
                        "intent": outputs.get("intent"),
                        "reasons": outputs.get("policy_reasons", []),
                    },
                )
                return {"sent": False, "handoff_required": True}, None, None

            sent, selector_used, selector_source = self._with_selector_ref(
                step["selector_ref"],
                attempted_selectors,
                lambda selector: apply_send_message(window, selector),
            )
            self.conversation_logger.record(
                "message_sent",
                contact_name=str(outputs.get("contact_name", "")),
                payload={
                    "intent": outputs.get("intent"),
                    "reply_text": outputs.get("reply_text"),
                    "sent": sent,
                },
            )
            return {"sent": sent, "handoff_required": False}, selector_used, selector_source

        raise ValueError(f"Unsupported desktop step type: {step_type}")

    def _with_selector_ref(
        self,
        selector_ref: str,
        attempted_selectors: list[str],
        action: Any,
    ) -> tuple[Any, str, str]:
        last_error = ""
        for candidate in self.selector_resolver.candidates_for(selector_ref):
            attempted_selectors.append(candidate.selector)
            try:
                result = action(candidate.selector)
                return result, candidate.selector, candidate.source
            except Exception as error:
                last_error = str(error)
        raise RuntimeError(last_error or f"selector not found: {selector_ref}")


class DesktopMessageExecutor:
    """Run a desktop message Skill end-to-end."""

    def __init__(self, *, storage_root: Path, browser: Any | None = None):
        self.storage_root = storage_root
        self.browser = browser

    def run(self, skill: Any, *, page: Any | None = None) -> DesktopRunResult:
        run_id = str(uuid.uuid4())
        logger = RunLogger(run_id, self.storage_root / "runs")
        observer = ScreenshotObserver(self.storage_root / "snapshots")
        session = AppFinder().find_window(
            runtime=skill.runtime,
            page=page,
            browser=self.browser,
            window_title_regex=str(skill.raw.get("desktop", {}).get("window_title_regex", "WeChat|微信")),
        )
        outputs: dict[str, Any] = {}
        steps: list[StepResult] = []
        runner = DesktopStepRunner(skill=skill, storage_root=self.storage_root)
        logger.write("run_started", {"skill_id": skill.id, "skill_version": skill.version, "runtime": skill.runtime})

        try:
            for step in skill.steps:
                logger.write("step_started", {"step": step})
                result = runner.run(session.window, step, outputs=outputs)
                steps.append(result)
                logger.write("step_finished", result.to_dict())
                if result.status == "failed":
                    window_state = {}
                    if hasattr(session.window, "state"):
                        try:
                            window_state = dict(session.window.state())
                        except Exception:
                            window_state = {}
                    snapshot = observer.screenshot_on_failure(
                        run_id=run_id,
                        step=step,
                        window=session.window,
                        error=RuntimeError(result.error or "desktop step failed"),
                        state={**window_state, **outputs},
                    )
                    logger.write("run_failed", {"failed_step_id": step["id"], "snapshot": snapshot.to_dict()})
                    return DesktopRunResult(
                        run_id=run_id,
                        skill_id=skill.id,
                        status="failed",
                        steps=steps,
                        outputs=outputs,
                        failure_snapshot=snapshot,
                    )
            logger.write("run_succeeded", {"step_count": len(steps), "outputs": outputs})
            return DesktopRunResult(run_id=run_id, skill_id=skill.id, status="success", steps=steps, outputs=outputs)
        finally:
            session.close()
