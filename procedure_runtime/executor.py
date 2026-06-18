"""Procedure Skill executor compatibility module."""

from rpa_runtime.executor import RPAExecutor, RunResult

ProcedureExecutor = RPAExecutor

__all__ = ["ProcedureExecutor", "RPAExecutor", "RunResult"]
