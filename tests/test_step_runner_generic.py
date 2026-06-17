from pathlib import Path
from types import SimpleNamespace

from rpa_runtime.executor import RPAExecutor
from rpa_runtime.selector_resolver import SelectorResolver
from rpa_runtime.step_runner import StepRunner


class GenericFakePage:
    def __init__(self):
        self.url = "about:blank"
        self.available_selectors = {
            "#button",
            "#name",
            "#status",
            "#orders",
            "#category",
        }
        self.clicked = []
        self.filled = []
        self.selected = []
        self.waited = []
        self.html = "<html><body><p id='status'>Ready</p><table id='orders'></table></body></html>"

    def goto(self, url):
        self.url = url

    def click(self, selector):
        self._require(selector)
        self.clicked.append(selector)

    def fill(self, selector, value):
        self._require(selector)
        self.filled.append((selector, value))

    def select_option(self, selector, value):
        self._require(selector)
        self.selected.append((selector, value))

    def wait_for_selector(self, selector, timeout=None):
        self._require(selector)
        self.waited.append((selector, timeout))

    def text_content(self, selector):
        self._require(selector)
        if selector == "#status":
            return "Ready"
        return ""

    def eval_on_selector(self, selector, expression):
        self._require(selector)
        return [
            ["Order ID", "Total"],
            ["R-1001", "125.50"],
            ["R-1002", "88.00"],
        ]

    def screenshot(self, path, full_page=True):
        Path(path).write_bytes(b"fake screenshot")

    def content(self):
        return self.html

    def _require(self, selector):
        if selector not in self.available_selectors:
            raise RuntimeError(f"selector not found: {selector}")


def make_runner() -> StepRunner:
    selectors = {
        "button": {"primary": "#button", "fallbacks": []},
        "name": {"primary": "#name", "fallbacks": []},
        "status": {"primary": "#status", "fallbacks": []},
        "orders": {"primary": "#orders", "fallbacks": []},
        "category": {"primary": "#category", "fallbacks": []},
    }
    return StepRunner(SelectorResolver(selectors))


def test_step_goto(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {"id": "open", "type": "goto", "goal": "Open page", "url": "https://example.test/report"},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert result.step_type == "goto"
    assert page.url == "https://example.test/report"


def test_step_fill(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {"id": "fill_name", "type": "fill", "goal": "Fill name", "selector_ref": "name", "value": "Ada"},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert page.filled == [("#name", "Ada")]


def test_step_click(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {"id": "click_button", "type": "click", "goal": "Click", "selector_ref": "button"},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert page.clicked == ["#button"]


def test_step_wait_for(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {"id": "wait_status", "type": "wait_for", "goal": "Wait", "selector_ref": "status", "timeout_ms": 500},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert page.waited == [("#status", 500)]


def test_step_select(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {"id": "select_category", "type": "select", "goal": "Select category", "selector_ref": "category", "value": "all"},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert page.selected == [("#category", "all")]


def test_step_extract_text(tmp_path):
    page = GenericFakePage()
    outputs = {}
    result = make_runner().run(
        page,
        {
            "id": "read_status",
            "type": "extract_text",
            "goal": "Read status",
            "selector_ref": "status",
            "output_key": "status_text",
        },
        outputs=outputs,
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert result.outputs == {"status_text": "Ready"}
    assert outputs["status_text"] == "Ready"


def test_step_extract_table(tmp_path):
    page = GenericFakePage()
    outputs = {}
    result = make_runner().run(
        page,
        {
            "id": "extract_orders",
            "type": "extract_table",
            "goal": "Extract orders",
            "selector_ref": "orders",
            "output_key": "orders",
            "row_count_output_key": "table_rows",
            "output_path": "orders.csv",
            "output_path_key": "csv_path",
            "has_header": True,
        },
        outputs=outputs,
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert outputs["table_rows"] == 2
    assert Path(outputs["csv_path"]).exists()
    assert "R-1001" in Path(outputs["csv_path"]).read_text(encoding="utf-8")


def test_step_assert_text(tmp_path):
    page = GenericFakePage()
    result = make_runner().run(
        page,
        {
            "id": "assert_ready",
            "type": "assert_text",
            "goal": "Assert ready",
            "selector_ref": "status",
            "expected_text": "Ready",
        },
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"


def test_step_screenshot(tmp_path):
    page = GenericFakePage()
    outputs = {}
    result = make_runner().run(
        page,
        {
            "id": "capture_page",
            "type": "screenshot",
            "goal": "Capture page",
            "output_path": "page.png",
            "output_key": "page_screenshot",
        },
        outputs=outputs,
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert Path(outputs["page_screenshot"]).exists()


def test_step_download_file(tmp_path):
    page = GenericFakePage()
    outputs = {}
    result = make_runner().run(
        page,
        {
            "id": "download_report",
            "type": "download_file",
            "goal": "Download report",
            "selector_ref": "button",
            "output_path": "report.csv",
            "output_key": "download_path",
            "simulated_content": "id,total\n1,100\n",
        },
        outputs=outputs,
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"
    assert Path(outputs["download_path"]).read_text(encoding="utf-8") == "id,total\n1,100\n"


def test_step_assert_url(tmp_path):
    page = GenericFakePage()
    page.url = "https://example.test/reports"
    result = make_runner().run(
        page,
        {"id": "assert_url", "type": "assert_url", "goal": "Assert URL", "url_contains": "/reports"},
        storage_root=tmp_path,
        run_id="run-1",
    )

    assert result.status == "success"


def test_skill_outputs(tmp_path):
    page = GenericFakePage()
    skill = SimpleNamespace(
        id="output_demo",
        name="Output Demo",
        version="0.1.0",
        selectors={
            "status": {"primary": "#status", "fallbacks": []},
            "orders": {"primary": "#orders", "fallbacks": []},
        },
        repair_policy={"retry": {"max_attempts": 1, "delay_seconds": 0}},
        steps=[
            {
                "id": "read_status",
                "type": "extract_text",
                "goal": "Read status",
                "selector_ref": "status",
                "output_key": "extracted_text",
            },
            {
                "id": "extract_orders",
                "type": "extract_table",
                "goal": "Extract orders",
                "selector_ref": "orders",
                "output_key": "orders",
                "row_count_output_key": "table_rows",
                "has_header": True,
            },
        ],
    )

    result = RPAExecutor(storage_root=tmp_path).run(skill, page=page)

    assert result.status == "success"
    assert result.outputs["extracted_text"] == "Ready"
    assert result.outputs["table_rows"] == 2
