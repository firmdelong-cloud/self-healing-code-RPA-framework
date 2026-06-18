"""Minimal event loop for event Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .action_policy import ActionPolicy
from .context_builder import ContextBuilder
from .decision_engine import DecisionEngine
from .event_detector import EventDetector
from .memory_store import EventMemoryStore


@dataclass(frozen=True)
class EventLoopResult:
    """Result of a single event loop poll."""

    status: str
    processed: int
    actions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "processed": self.processed,
            "actions": list(self.actions),
        }


class EventLoop:
    """Run one bounded poll of an event Skill.

    Long-running scheduling is intentionally outside this class. The runtime
    stays testable by processing one batch of adapter events at a time.
    """

    def __init__(
        self,
        *,
        detector: EventDetector,
        context_builder: ContextBuilder,
        memory_store: EventMemoryStore,
        decision_engine: DecisionEngine | None = None,
        action_policy: ActionPolicy | None = None,
    ):
        self.detector = detector
        self.context_builder = context_builder
        self.memory_store = memory_store
        self.decision_engine = decision_engine or DecisionEngine()
        self.action_policy = action_policy or ActionPolicy()

    def poll(self, *, decision_policy: dict[str, Any], reply_policy: dict[str, Any], max_events: int = 10) -> EventLoopResult:
        actions: list[dict[str, Any]] = []
        for event in self.detector.detect()[:max_events]:
            memory = self.memory_store.load(event.event_id)
            context = self.context_builder.build(event)
            context["already_handled"] = bool(memory.get("handled"))
            decision = self.decision_engine.decide(
                event=event.payload,
                context=context,
                policy=decision_policy,
            )
            action = self.action_policy.evaluate(decision=decision, policy=reply_policy)
            payload = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "subject_id": event.subject_id,
                "decision": decision.to_dict(),
                "action": action.to_dict(),
                "context": context,
            }
            actions.append(payload)
            if action.allowed:
                self.memory_store.mark_handled(event.event_id, payload)
        return EventLoopResult(status="ok", processed=len(actions), actions=actions)
