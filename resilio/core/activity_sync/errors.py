"""Activity-sync domain errors."""


class ActivitySyncError(RuntimeError):
    """A sync invariant failed and the staged run cannot be committed."""
