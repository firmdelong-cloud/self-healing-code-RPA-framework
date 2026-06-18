"""Locate desktop windows or open mock pages for desktop Skills."""

from __future__ import annotations

import re
import subprocess
from typing import Any

from rpa_runtime.browser import PlaywrightBrowser

from .window_controller import DesktopSession, LiveWechatWindow, MockDesktopWindow


class AppFinder:
    """Create a desktop window session from the Skill runtime."""

    WECHAT_PROCESS_NAMES = {"WeChat", "WeChatAppEx", "Weixin"}
    BLOCKED_PROCESS_NAMES = {"WXWork", "WXWorkWeb", "WXWorkXNet"}

    def find_window(
        self,
        *,
        runtime: str,
        page: Any | None = None,
        browser: PlaywrightBrowser | None = None,
        window_title_regex: str = "WeChat|微信",
    ) -> DesktopSession:
        if page is not None:
            if hasattr(page, "detect_unread") and hasattr(page, "click_chat"):
                return DesktopSession(window=page)
            return DesktopSession(window=MockDesktopWindow(page))

        if runtime == "desktop_mock":
            session = (browser or PlaywrightBrowser(headless=True)).start()
            return DesktopSession(window=MockDesktopWindow(session.page), closer=session.close)

        if runtime in {"desktop_wechat", "wechat_desktop"}:
            return DesktopSession(window=self._find_live_wechat(window_title_regex))

        raise ValueError(f"Unsupported desktop runtime: {runtime}")

    def _find_live_wechat(self, window_title_regex: str) -> LiveWechatWindow:
        try:
            from pywinauto import Desktop  # type: ignore
        except ImportError as error:
            raise RuntimeError(
                "pywinauto is required for live WeChat desktop automation. "
                "Install it with `pip install pywinauto`."
            ) from error

        desktop = Desktop(backend="uia")
        title_pattern = re.compile(window_title_regex) if window_title_regex else None
        windows = []
        for candidate in desktop.windows(visible_only=True):
            candidate_pid = candidate.process_id()
            if candidate_pid is None:
                continue
            process_name = self._process_name_for_pid(int(candidate_pid))
            if process_name in self.BLOCKED_PROCESS_NAMES:
                continue
            title = (candidate.window_text() or "").strip()
            title_matches = bool(title_pattern.search(title)) if title_pattern and title else False
            if process_name in self.WECHAT_PROCESS_NAMES or title_matches:
                windows.append(candidate)

        if not windows:
            raise RuntimeError(
                "Could not find a visible personal WeChat window. "
                "Please open the official WeChat desktop chat window and bring it to the foreground."
            )

        preferred = [
            candidate
            for candidate in windows
            if candidate.process_id() is not None
            and self._process_name_for_pid(int(candidate.process_id())) in self.WECHAT_PROCESS_NAMES
        ]
        window = preferred[0] if preferred else windows[0]
        window.set_focus()
        return LiveWechatWindow(window)

    def _process_name_for_pid(self, pid: int) -> str:
        command = (
            f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty ProcessName"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip()
