"""Runtime exceptions."""


class RPAError(Exception):
    """Base runtime error."""


class SkillLoadError(RPAError):
    """Raised when a skill cannot be loaded."""


class SelectorNotFoundError(RPAError):
    """Raised when no selector candidate can complete a step."""

    def __init__(self, selector_ref: str, attempted_selectors: list[str], last_error: str):
        self.selector_ref = selector_ref
        self.attempted_selectors = attempted_selectors
        self.last_error = last_error
        super().__init__(
            f"Selector '{selector_ref}' failed. "
            f"Attempted: {attempted_selectors}. Last error: {last_error}"
        )


class HumanConfirmationRequired(RPAError):
    """Raised when a high-risk step is blocked pending human approval."""


class StepExecutionError(RPAError):
    """Raised when a step fails after deterministic recovery."""

    def __init__(self, step_id: str, goal: str, original_error: Exception):
        self.step_id = step_id
        self.goal = goal
        self.original_error = original_error
        super().__init__(f"Step '{step_id}' failed: {original_error}")

