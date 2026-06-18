"""Standard component protocol for Automation Skill Engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Protocol


class ComponentCallable(Protocol):
    """Callable shape implemented by every component."""

    def __call__(self, context: Any, inputs: dict[str, Any]) -> "ComponentRunResult":
        """Run the component with a context and validated inputs."""


@dataclass(frozen=True)
class ComponentRunResult:
    """Result returned by a component implementation."""

    outputs: dict[str, Any] = field(default_factory=dict)
    selector_used: str | None = None
    selector_source: str | None = None
    attempted_selectors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComponentDefinition:
    """Declarative metadata plus executable component callable."""

    id: str
    name: str
    category: str
    description: str
    inputs_schema: dict[str, Any]
    outputs_schema: dict[str, Any]
    errors: list[str]
    repairable: bool
    repair_scope: str
    risk_level: str
    run: Callable[[Any, dict[str, Any]], ComponentRunResult]

    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "inputs_schema": self.inputs_schema,
            "outputs_schema": self.outputs_schema,
            "errors": self.errors,
            "repairable": self.repairable,
            "repair_scope": self.repair_scope,
            "risk_level": self.risk_level,
        }
