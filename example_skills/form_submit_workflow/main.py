"""Entrypoint for the form_submit_workflow Skill."""

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


def fixture_url() -> str:
    return (PROJECT_ROOT / "tests" / "fixtures" / "form_demo.html").resolve().as_uri()


def prepare_skill(skill: SkillDefinition, demo_url: str | None = None) -> SkillDefinition:
    resolved_steps = []
    for step in skill.steps:
        resolved_step = dict(step)
        if resolved_step.get("url") == "{{FORM_DEMO_URL}}":
            resolved_step["url"] = demo_url or fixture_url()
        resolved_steps.append(resolved_step)
    return replace(skill, steps=resolved_steps)


def run(page: Any | None = None, storage_root: Path | None = None) -> RunResult:
    skill = prepare_skill(SkillLoader().load(Path(__file__).with_name("skill.yaml")))
    executor = RPAExecutor(
        storage_root=storage_root or PROJECT_ROOT / "storage",
        browser=PlaywrightBrowser(headless=True),
    )
    return executor.run(skill, page=page)


if __name__ == "__main__":
    print(run().to_dict())
