import json
from pathlib import Path

from example_skills.web_report_export.main import prepare_skill
from rpa_runtime.executor import RPAExecutor
from skill_registry.loader import SkillLoader


class FakePage:
    def __init__(self, available_selectors=None):
        self.available_selectors = set(available_selectors or [])
        self.url = "about:blank"
        self.html = """
        <html>
          <body>
            <input id="username" />
            <input id="password" />
            <button id="login-submit">Sign in</button>
            <a id="report-page-link">Reports</a>
            <input id="date-start" />
            <input id="date-end" />
            <button data-testid="export-button">Export Report</button>
            <p id="export-success">Export ready</p>
          </body>
        </html>
        """
        self.clicked = []
        self.filled = []
        self.waited = []

    def goto(self, url):
        self.url = url

    def click(self, selector):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")
        self.clicked.append(selector)

    def fill(self, selector, value):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")
        self.filled.append((selector, value))

    def wait_for_selector(self, selector):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")
        self.waited.append(selector)

    def screenshot(self, path, full_page=True):
        Path(path).write_bytes(b"fake screenshot")

    def content(self):
        return self.html


def load_demo_skill():
    skill = SkillLoader().load("example_skills/web_report_export/skill.yaml")
    fixture_url = Path(__file__).resolve().parent / "fixtures" / "report_demo.html"
    fixture_url = fixture_url.as_uri()
    return prepare_skill(skill, fixture_url)


def successful_selectors():
    return {
        "#username",
        "#password",
        "#login-submit",
        "#report-page-link",
        "#date-start",
        "#date-end",
        "button[data-testid='export-button']",
        "#export-success",
    }


def test_skill_can_be_loaded():
    skill = load_demo_skill()

    assert skill.id == "web_report_export"
    assert skill.version == "0.2.0"
    assert [step["id"] for step in skill.steps] == [
        "open_login_page",
        "login",
        "enter_report_page",
        "select_date_range",
        "click_export",
        "verify_export_success",
    ]
    assert "export_button" in skill.selectors


def test_executor_runs_login_report_export_flow(tmp_path):
    skill = load_demo_skill()
    page = FakePage(available_selectors=successful_selectors())

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=page)

    assert result.status == "success"
    assert [step.status for step in result.steps] == ["success"] * 6
    assert page.filled == [
        ("#username", "demo_user"),
        ("#password", "demo_password"),
        ("#date-start", "2026-06-01"),
        ("#date-end", "2026-06-17"),
    ]
    assert "button[data-testid='export-button']" in page.clicked
    assert page.waited == ["#export-success"]
    assert (tmp_path / "runs" / f"{result.run_id}.jsonl").exists()


def test_click_export_primary_selector_fails_and_fallback_succeeds(tmp_path):
    skill = load_demo_skill()
    page = FakePage(available_selectors=successful_selectors())

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=page)

    click_export = next(step for step in result.steps if step.step_id == "click_export")
    assert result.status == "success"
    assert click_export.selector_used == "button[data-testid='export-button']"
    assert click_export.selector_source == "fallback"
    assert click_export.attempted_selectors == [
        "#export-button-primary-missing",
        "button[data-testid='export-button']",
    ]


def test_all_export_selectors_fail_generates_snapshot_and_repair_request(tmp_path):
    skill = load_demo_skill()
    skill.selectors["export_button"] = {
        "primary": "#missing-export-primary",
        "fallbacks": ["#missing-export-fallback", "text=Missing Export"],
    }
    page = FakePage(available_selectors=successful_selectors() - {"button[data-testid='export-button']"})

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=page)

    assert result.status == "failed"
    assert result.failure_snapshot is not None
    assert result.repair_request_path is not None
    assert Path(result.failure_snapshot.metadata_path).exists()
    assert Path(result.failure_snapshot.screenshot_path).exists()
    assert Path(result.failure_snapshot.dom_path).exists()

    repair_request = json.loads(Path(result.repair_request_path).read_text(encoding="utf-8"))
    assert repair_request["run_id"] == result.run_id
    assert repair_request["skill_id"] == "web_report_export"
    assert repair_request["skill_name"] == "Web Report Export"
    assert repair_request["skill_version"] == "0.2.0"
    assert repair_request["failed_step_id"] == "click_export"
    assert repair_request["failed_step_goal"] == "Click the export button to generate the report."
    assert repair_request["error_type"] == "SelectorResolutionError"
    assert "selector not found" in repair_request["error_message"]
    assert repair_request["current_url"].startswith("file:///")
    assert '"id": "click_export"' in repair_request["original_code_snippet"]
    assert repair_request["original_selector"] == "#missing-export-primary"
    assert repair_request["fallback_selectors"] == ["#missing-export-fallback", "text=Missing Export"]
    assert repair_request["recent_success_snapshot_path"] is None
    assert Path(repair_request["screenshot_path"]).exists()
    assert Path(repair_request["dom_snapshot_path"]).exists()
    assert repair_request["allowed_repair_scope"]["scope_type"] == "selector_only"
    assert repair_request["allowed_repair_scope"]["failed_step_id"] == "click_export"
    assert repair_request["allowed_repair_scope"]["allowed_files"] == [
        "example_skills/web_report_export/selectors.yaml"
    ]
    assert repair_request["allowed_repair_scope"]["allowed_selector_refs"] == ["export_button"]
    assert repair_request["allowed_repair_scope"]["must_not_touch_other_steps"] is True
    assert repair_request["allowed_repair_scope"]["must_not_touch_runtime"] is True
    assert "rewrite_entire_skill" in repair_request["forbidden_actions"]
    assert repair_request["human_approval_required"] is False
    assert repair_request["test_command"] == ["python", "-m", "pytest"]
    assert repair_request["rollback_version"] == "0.2.0"
    assert repair_request["risk_level"] == "medium"
