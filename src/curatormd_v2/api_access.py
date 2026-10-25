"""Host-owned project authorization and request-limiting primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from threading import Lock
import time
from typing import Callable, Iterable, Protocol


PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_PROJECT_ID_RE = PROJECT_ID_PATTERN
_SUBJECT_ID_RE = PROJECT_ID_PATTERN
MAX_TRACKED_CALLERS = 10_000


class ProjectAction(StrEnum):
    """Authorization scopes required by the transport-neutral operations."""

    READ = "read"
    WRITE = "write"
    REVIEW = "review"
    PURGE_RETRY = "purge_retry"
    RETENTION_HOLD_RELEASE = "retention_hold_release"
    EVENT_RETRY = "event_retry"


@dataclass(frozen=True, slots=True)
class AuthenticatedCaller:
    """Opaque identity asserted by a trusted host authentication adapter.

    Constructing this value is not authentication. Network/MCP transports must
    obtain it from their verified session context and must never deserialize it
    directly from caller-controlled request data.
    """

    subject_id: str
    profile_id: str | None = None

    def __post_init__(self) -> None:
        if not _SUBJECT_ID_RE.fullmatch(self.subject_id):
            raise ValueError("subject_id must be a bounded opaque identifier")
        if self.profile_id is not None and not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", self.profile_id
        ):
            raise ValueError("profile_id must be a bounded opaque identifier")


class ProjectAuthorizer(Protocol):
    """Host-owned authorization for an identity, project, and operation."""

    # pylint: disable=too-few-public-methods  # Protocol intentionally has one authorization operation.

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Return true only when the verified caller has this project scope."""
        ...


class RejectAllProjectAccess:
    """Safe default until Hermes supplies an authorization adapter."""

    # pylint: disable=too-few-public-methods  # Fail-closed policy implements the one-method protocol.

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Deny every request until a host-owned authorizer is configured."""

        del caller, project_id, action
        return False


class ProjectGrantAuthorizer:
    """Authorize exact verified-subject/project/action grants in this process.

    This is a reference policy adapter, not an identity provider or durable
    project registry. A trusted host must supply verified subjects and
    operator-managed grants; unknown triples always deny.
    """

    # pylint: disable=too-few-public-methods  # This exact-grant policy implements one authorization operation.

    def __init__(
        self,
        grants: Iterable[tuple[object, object, object]],
    ) -> None:
        checked: set[tuple[str, str, ProjectAction]] = set()
        for grant in grants:
            subject_id, project_id, action = grant
            if not isinstance(subject_id, str) or not _SUBJECT_ID_RE.fullmatch(
                subject_id
            ):
                raise ValueError("project grant subject must be a bounded opaque ID")
            if not isinstance(project_id, str) or not _PROJECT_ID_RE.fullmatch(
                project_id
            ):
                raise ValueError("project grant project must be a bounded opaque ID")
            if not isinstance(action, ProjectAction):
                raise ValueError("project grant action must be a known ProjectAction")
            checked.add((subject_id, project_id, action))
        self._grants = frozenset(checked)

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Return true only for an exact subject, project, and action grant."""

        return (caller.subject_id, project_id, action) in self._grants


class RequestLimiter(Protocol):
    """Bound request rate by verified subject and project."""

    # pylint: disable=too-few-public-methods  # Protocol intentionally has one rate-limit operation.

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume one request token, if available."""
        ...


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float
    touched_at: float


class InMemoryTokenBucket:
    """Small per-process limiter for local adapters and tests.

    Production deployments with multiple workers must inject a shared limiter;
    this class does not claim cross-process enforcement.
    """

    # pylint: disable=too-few-public-methods  # The limiter contract is one token-consumption operation.

    def __init__(
        self,
        capacity: int = 120,
        refill_period_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity < 1 or refill_period_seconds <= 0:
            raise ValueError("rate limit capacity and refill period must be positive")
        self.capacity = capacity
        self.refill_rate = capacity / refill_period_seconds
        self.clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = Lock()

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume one token for the verified subject and project pair."""

        now = self.clock()
        key = (subject_id, project_id)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= MAX_TRACKED_CALLERS:
                    self._prune_idle(now)
                if len(self._buckets) >= MAX_TRACKED_CALLERS:
                    return False
                self._buckets[key] = _Bucket(self.capacity - 1, now, now)
                self._prune_idle(now)
                return True
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_rate)
            bucket.updated_at = now
            bucket.touched_at = now
            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            self._prune_idle(now)
            return True

    def _prune_idle(self, now: float) -> None:
        if len(self._buckets) <= MAX_TRACKED_CALLERS:
            return
        expiry = now - max(60.0, 2.0 / self.refill_rate)
        self._buckets = {
            bucket_key: entry
            for bucket_key, entry in self._buckets.items()
            if entry.touched_at >= expiry
        }
