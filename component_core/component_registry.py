"""Registry for reusable automation components."""

from __future__ import annotations

from dataclasses import dataclass, field

from .component_schema import ComponentDefinition


class ComponentNotFoundError(KeyError):
    """Raised when a Skill references an unknown component."""


@dataclass
class ComponentRegistry:
    """In-memory registry of component definitions."""

    _components: dict[str, ComponentDefinition] = field(default_factory=dict)

    def register(self, component: ComponentDefinition) -> None:
        self._components[component.id] = component

    def get(self, component_id: str) -> ComponentDefinition:
        try:
            return self._components[component_id]
        except KeyError as error:
            raise ComponentNotFoundError(f"Component is not registered: {component_id}") from error

    def list_component_ids(self) -> list[str]:
        return sorted(self._components)

    def all(self) -> list[ComponentDefinition]:
        return [self._components[component_id] for component_id in self.list_component_ids()]
