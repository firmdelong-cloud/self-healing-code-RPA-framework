"""Desktop message runtime for controlled chat automation."""

from .app_finder import AppFinder
from .desktop_step_runner import DesktopMessageExecutor, DesktopRunResult, DesktopStepRunner
from .screenshot_observer import DesktopFailureSnapshot, ScreenshotObserver
from .window_controller import DesktopRuntimeError, DesktopSession, LiveWechatWindow, MockDesktopWindow

__all__ = [
    "AppFinder",
    "DesktopFailureSnapshot",
    "DesktopMessageExecutor",
    "DesktopRunResult",
    "DesktopRuntimeError",
    "DesktopSession",
    "DesktopStepRunner",
    "LiveWechatWindow",
    "MockDesktopWindow",
    "ScreenshotObserver",
]
