"""Locate desktop windows or open mock pages for desktop Skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rpa_runtime.browser import PlaywrightBrowser

from .window_controller import DesktopSession, LiveWechatWindow, MockDesktopWindow


class AppFinder:
    """Create a desktop window session from the Skill runtime."""

    def find_window(
        self,
        *,
        runtime: str,
        page: Any | None = None,
        browser: PlaywrightBrowser | None = None,
        window_title_regex: str = "微信|WeChat",
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
        windows = desktop.windows(title_re=window_title_regex, visible_only=True)
        if not windows:
            raise RuntimeError(f"Could not find a visible WeChat window matching: {window_title_regex}")
        window = windows[0]
        window.set_focus()
        return LiveWechatWindow(window)
