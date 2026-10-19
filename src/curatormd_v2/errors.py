"""Stable, sanitized version-1 errors for future Curator transports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .reviews import ReviewAuthorizationError
from .store import (
    ConflictError,
    EventInboxCapacityError,
    EventOrderError,
    FactCapacityError,
    GoalListCapacityError,
    NotFoundError,
)


ERROR_SCHEMA_VERSION = 1


class APIErrorCode(StrEnum):
    """Stable machine-readable categories; never encode exception text here."""

    INVALID_REQUEST = "invalid_request"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


_PUBLIC_MESSAGES = {
    APIErrorCode.INVALID_REQUEST: "The request is invalid.",
    APIErrorCode.FORBIDDEN: "The caller is not allowed to perform this operation.",
    APIErrorCode.NOT_FOUND: "The requested record was not found.",
    APIErrorCode.CONFLICT: "The request conflicts with current project state.",
    APIErrorCode.CAPACITY_EXCEEDED: "A project capacity limit has been reached.",
    APIErrorCode.RATE_LIMITED: "The request rate limit has been reached.",
    APIErrorCode.INTERNAL_ERROR: "The request could not be completed.",
}


@dataclass(frozen=True, slots=True)
class APIError:
    """Transport-neutral, versioned error envelope with a safe public message."""

    code: APIErrorCode
    message: str
    schema_version: int = ERROR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or self.schema_version != ERROR_SCHEMA_VERSION
        ):
            raise ValueError(f"unsupported error schema version: {self.schema_version}")
        try:
            code = APIErrorCode(self.code)
        except ValueError as exc:
            raise ValueError("unsupported API error code") from exc
        object.__setattr__(self, "code", code)
        if self.message != _PUBLIC_MESSAGES[code]:
            raise ValueError("API error message must use the stable public text")

    def to_dict(self) -> dict[str, int | str]:
        """Return the stable wire representation for HTTP or MCP adapters."""

        return {
            "schema_version": self.schema_version,
            "code": self.code.value,
            "message": self.message,
        }


class RateLimitExceeded(RuntimeError):
    """The caller exhausted its configured request budget."""


def to_api_error(error: Exception) -> APIError:
    """Map domain failures to stable codes without exposing internal details."""

    if isinstance(error, RateLimitExceeded):
        code = APIErrorCode.RATE_LIMITED
    elif isinstance(
        error,
        (EventInboxCapacityError, FactCapacityError, GoalListCapacityError),
    ):
        code = APIErrorCode.CAPACITY_EXCEEDED
    elif isinstance(error, (ReviewAuthorizationError, PermissionError)):
        code = APIErrorCode.FORBIDDEN
    elif isinstance(error, NotFoundError):
        code = APIErrorCode.NOT_FOUND
    elif isinstance(error, (EventOrderError, ConflictError)):
        code = APIErrorCode.CONFLICT
    elif isinstance(error, ValueError):
        code = APIErrorCode.INVALID_REQUEST
    else:
        code = APIErrorCode.INTERNAL_ERROR

    return APIError(code=code, message=_PUBLIC_MESSAGES[code])
