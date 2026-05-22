class DomainError(Exception):
    """Base class for all domain errors."""


class IncidentNotFoundError(DomainError):
    """Raised when an incident cannot be found by the given identifier."""


class DuplicateIncidentError(DomainError):
    """Raised when an incident with the same fingerprint already exists."""
