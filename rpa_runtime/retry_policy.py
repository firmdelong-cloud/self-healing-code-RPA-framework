"""Retry policy primitives."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    delay_seconds: float = 0.0

    @classmethod
    def from_dict(cls, data: dict | None) -> "RetryPolicy":
        data = data or {}
        return cls(
            max_attempts=max(1, int(data.get("max_attempts", 1))),
            delay_seconds=max(0.0, float(data.get("delay_seconds", 0.0))),
        )

    def wait_before_retry(self, attempt_index: int) -> None:
        if attempt_index > 0 and self.delay_seconds:
            time.sleep(self.delay_seconds)

