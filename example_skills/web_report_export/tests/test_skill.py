from pathlib import Path
import importlib.util

import pytest


SKILL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("web_report_export_main", SKILL_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run = module.run


@pytest.mark.integration
def test_demo_skill_entrypoint_runs_against_local_html(tmp_path):
    result = run(storage_root=tmp_path)

    assert result.status == "success"
    assert [step.step_id for step in result.steps] == [
        "open_login_page",
        "login",
        "enter_report_page",
        "select_date_range",
        "click_export",
        "verify_export_success",
    ]
    click_export = next(step for step in result.steps if step.step_id == "click_export")
    assert click_export.selector_source == "fallback"
    assert click_export.selector_used == "button[data-testid='export-button']"
