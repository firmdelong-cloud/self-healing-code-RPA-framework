"""Resolve primary and fallback selectors."""

from __future__ import annotations

from dataclasses import dataclass

from rpa_runtime.exceptions import SelectorNotFoundError


@dataclass(frozen=True)
class SelectorCandidate:
    selector: str
    source: str


class SelectorResolver:
    def __init__(self, selectors: dict):
        self.selectors = selectors or {}

    def candidates_for(self, selector_ref: str) -> list[SelectorCandidate]:
        raw = self.selectors.get(selector_ref)
        if not raw:
            raise SelectorNotFoundError(selector_ref, [], "selector ref is not defined")

        candidates: list[SelectorCandidate] = []
        primary = raw.get("primary")
        if primary:
            candidates.append(SelectorCandidate(selector=primary, source="primary"))

        for fallback in raw.get("fallbacks", []) or []:
            candidates.append(SelectorCandidate(selector=fallback, source="fallback"))

        if not candidates:
            raise SelectorNotFoundError(selector_ref, [], "selector has no candidates")

        return candidates

