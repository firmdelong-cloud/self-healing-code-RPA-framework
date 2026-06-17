import pytest

from rpa_runtime.exceptions import SelectorNotFoundError
from rpa_runtime.selector_resolver import SelectorResolver


def test_selector_resolver_returns_primary_then_fallbacks():
    resolver = SelectorResolver(
        {
            "export_button": {
                "primary": "#export-report",
                "fallbacks": ["button[data-testid='export-report']", "text=Export"],
            }
        }
    )

    selectors = resolver.candidates_for("export_button")

    assert [item.selector for item in selectors] == [
        "#export-report",
        "button[data-testid='export-report']",
        "text=Export",
    ]
    assert [item.source for item in selectors] == ["primary", "fallback", "fallback"]


def test_selector_resolver_raises_for_missing_ref():
    resolver = SelectorResolver({})

    with pytest.raises(SelectorNotFoundError):
        resolver.candidates_for("missing")

