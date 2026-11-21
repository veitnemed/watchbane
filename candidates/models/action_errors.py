"""Domain errors raised when changing the state of a title."""


class CandidateActionIdentityConflict(ValueError):
    """An untyped candidate would overwrite an independent legacy action."""
