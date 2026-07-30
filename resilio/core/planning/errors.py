"""Planning application errors."""


class PlanOperationError(RuntimeError):
    """A planning transition could not be proven safe."""
