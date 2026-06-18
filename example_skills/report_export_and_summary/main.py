"""Entrypoint for the report_export_and_summary Skill."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rpa_runtime.browser import PlaywrightBrowser
from rpa_runtime.executor import RPAExecutor, RunResult
from skill_registry.loader import SkillDefinition, SkillLoader


def report_demo_url() -> str:
    return (PROJECT_ROOT / "tests" / "fixtures" / "report_demo.html").resolve().as_uri()


def prepare_skill(skill: SkillDefinition, demo_url: str | None = None) -> SkillDefinition:
    resolved_url = demo_url or report_demo_url()
    resolved_nodes = []
    for node in skill.nodes:
        resolved_node = dict(node)
        inputs = dict(resolved_node.get("inputs", {}) or {})
        if inputs.get("url") == "{{REPORT_DEMO_URL}}":
            inputs["url"] = resolved_url
            resolved_node["inputs"] = inputs
        resolved_nodes.append(resolved_node)
    return replace(skill, nodes=resolved_nodes)


def run(page: Any | None = None, storage_root: Path | None = None) -> RunResult:
    skill_path = Path(__file__).with_name("skill.yaml")
    skill = prepare_skill(SkillLoader().load(skill_path))
    executor = RPAExecutor(
        storage_root=storage_root or PROJECT_ROOT / "storage",
        browser=PlaywrightBrowser(headless=True),
    )
    return executor.run(skill, page=page)


if __name__ == "__main__":
    print(run().to_dict())
