"""Experimental WeChat adapter.

This adapter is intentionally outside the core runtime. It is a desktop vision
integration point for Event Skills, not a Procedure Skill implementation.
"""

from .adapter import WeChatAdapter

__all__ = ["WeChatAdapter"]
