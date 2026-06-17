"""Playwright browser wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any

    def close(self) -> None:
        self.context.close()
        self.browser.close()
        self.playwright.stop()


class PlaywrightBrowser:
    def __init__(self, *, headless: bool = True, browser_name: str = "chromium"):
        self.headless = headless
        self.browser_name = browser_name

    def start(self) -> BrowserSession:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser_type = getattr(playwright, self.browser_name)
        browser = browser_type.launch(headless=self.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        return BrowserSession(playwright=playwright, browser=browser, context=context, page=page)

