"""Entrypoint for the wechat_auto_reply_live Skill."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import os
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop_runtime import DesktopMessageExecutor
from rpa_runtime.browser import PlaywrightBrowser
from skill_registry.loader import SkillDefinition, SkillLoader


def prepare_skill(skill: SkillDefinition, window_title_regex: str | None = None) -> SkillDefinition:
    raw = dict(skill.raw)
    desktop = dict(raw.get("desktop", {}) or {})
    if window_title_regex:
        desktop["window_title_regex"] = window_title_regex
    raw["desktop"] = desktop
    return replace(skill, raw=raw)


def run(
    *,
    page: Any | None = None,
    storage_root: Path | None = None,
    scenario: str | None = None,
    window_title_regex: str | None = None,
) -> Any:
    env_window_title = os.environ.get("WECHAT_WINDOW_TITLE_REGEX")
    skill = prepare_skill(
        SkillLoader().load(Path(__file__).with_name("skill.yaml")),
        window_title_regex=window_title_regex or env_window_title,
    )
    executor = DesktopMessageExecutor(
        storage_root=storage_root or PROJECT_ROOT / "storage",
        browser=PlaywrightBrowser(headless=True),
    )
    return executor.run(skill, page=page)


if __name__ == "__main__":
    print(run().to_dict())
