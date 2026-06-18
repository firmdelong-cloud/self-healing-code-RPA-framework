"""Capture desktop window screenshots and state dumps on failure."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
from typing import Any


@dataclass(frozen=True)
class DesktopFailureSnapshot:
    run_id: str
    step_id: str
    snapshot_dir: str
    screenshot_path: str | None
    state_path: str
    error_log: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScreenshotObserver:
    """Persist desktop failure evidence for later inspection."""

    def __init__(self, snapshot_root: Path):
        self.snapshot_root = snapshot_root
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

    def screenshot_on_failure(
        self,
        *,
        run_id: str,
        step: dict[str, Any],
        window: Any,
        error: Exception,
        state: dict[str, Any],
    ) -> DesktopFailureSnapshot:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        step_id = step.get("id", "unknown_step")
        snapshot_dir = self.snapshot_root / run_id / f"{timestamp}_{step_id}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_path = self._try_screenshot(window, snapshot_dir / "desktop.png")
        state_path = snapshot_dir / "state.json"
        payload = {
            "step": step,
            "state": state,
            "error_log": "".join(traceback.format_exception_only(type(error), error)).strip(),
            "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        }
        state_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return DesktopFailureSnapshot(
            run_id=run_id,
            step_id=step_id,
            snapshot_dir=str(snapshot_dir),
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            state_path=str(state_path),
            error_log=payload["error_log"],
        )

    def _try_screenshot(self, window: Any, path: Path) -> Path | None:
        if not hasattr(window, "screenshot"):
            return None
        try:
            window.screenshot(str(path))
            return path
        except Exception:
            return None
