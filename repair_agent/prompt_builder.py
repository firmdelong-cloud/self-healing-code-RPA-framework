"""Prompt construction placeholder for later repair integration."""

from __future__ import annotations

from typing import Any


class PromptBuilder:
    def build(self, repair_request: dict[str, Any]) -> str:
        return (
            "Repair only the failed step described in this request. "
            "Do not rewrite unrelated workflow code.\n\n"
            f"{repair_request}"
        )

