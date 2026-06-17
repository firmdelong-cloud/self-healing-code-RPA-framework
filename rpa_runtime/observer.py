"""Failure observation and snapshot persistence."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
from typing import Any


@dataclass(frozen=True)
class FailureSnapshot:
    run_id: str
    step_id: str
    snapshot_dir: str
    screenshot_path: str | None
    dom_path: str | None
    metadata_path: str
    current_url: str | None
    error_log: str


class Observer:
    def __init__(self, snapshot_root: Path):
        self.snapshot_root = snapshot_root
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

    def capture_failure(
        self,
        *,
        run_id: str,
        step: dict[str, Any],
        page: Any,
        error: Exception,
        attempted_selectors: list[str] | None = None,
    ) -> FailureSnapshot:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        step_id = step.get("id", "unknown_step")
        snapshot_dir = self.snapshot_root / run_id / f"{timestamp}_{step_id}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_path = self._try_screenshot(page, snapshot_dir / "screenshot.png")
        dom_path = self._try_dom(page, snapshot_dir / "dom.html")
        current_url = self._try_url(page)
        error_log = "".join(traceback.format_exception_only(type(error), error)).strip()

        metadata = {
            "run_id": run_id,
            "step": step,
            "current_url": current_url,
            "error_log": error_log,
            "attempted_selectors": attempted_selectors or [],
            "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        }
        metadata_path = snapshot_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        return FailureSnapshot(
            run_id=run_id,
            step_id=step_id,
            snapshot_dir=str(snapshot_dir),
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            dom_path=str(dom_path) if dom_path else None,
            metadata_path=str(metadata_path),
            current_url=current_url,
            error_log=error_log,
        )

    def _try_screenshot(self, page: Any, path: Path) -> Path | None:
        if not hasattr(page, "screenshot"):
            return None
        try:
            page.screenshot(path=str(path), full_page=True)
            return path
        except Exception:
            return None

    def _try_dom(self, page: Any, path: Path) -> Path | None:
        if not hasattr(page, "content"):
            return None
        try:
            path.write_text(page.content(), encoding="utf-8")
            return path
        except Exception:
            return None

    def _try_url(self, page: Any) -> str | None:
        try:
            return getattr(page, "url", None)
        except Exception:
            return None

    @staticmethod
    def to_dict(snapshot: FailureSnapshot) -> dict[str, Any]:
        return asdict(snapshot)

