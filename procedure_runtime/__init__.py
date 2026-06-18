"""Procedure Skill runtime.

This package names the existing deterministic RPA runtime explicitly. The
legacy rpa_runtime package remains as the implementation and compatibility
surface.
"""

from rpa_runtime.executor import RPAExecutor, RunResult
from rpa_runtime.selector_resolver import SelectorResolver
from rpa_runtime.step_runner import StepResult, StepRunner

ProcedureExecutor = RPAExecutor

__all__ = [
    "ProcedureExecutor",
    "RPAExecutor",
    "RunResult",
    "SelectorResolver",
    "StepResult",
    "StepRunner",
]
