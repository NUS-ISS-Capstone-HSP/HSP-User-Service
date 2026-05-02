class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Raised when input validation fails."""


class NotFoundError(DomainError):
    """Raised when entity does not exist."""


class ConflictError(DomainError):
    """Raised when entity conflicts with existing data."""


class AuthenticationError(DomainError):
    """Raised when authentication fails."""


class AuthorizationError(DomainError):
    """Raised when authorization fails."""
