"""Shared request-rate limiting for workers using the same SQLite backend."""

from __future__ import annotations

from collections.abc import Callable
import math
import re
import sqlite3
import time

from .store import CuratorStore
from .validation import is_exact_int, is_exact_number


_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
MAX_TRACKED_BUCKETS = 10_000
MAX_BUCKET_CAPACITY = 1_000_000
MIN_REFILL_PERIOD_SECONDS = 0.001
MAX_REFILL_PERIOD_SECONDS = 31_536_000.0


class SQLiteTokenBucket:  # pylint: disable=too-few-public-methods
    """Atomically enforce one bucket per authenticated subject/project pair.

    Instances share quota when they use different connections to the same
    SQLite database. State is bounded and idle buckets can be discarded only
    after they would have refilled to capacity. The bucket table contains opaque
    authorization identifiers only; no request content is stored.
    """

    def __init__(
        self,
        store: CuratorStore,
        *,
        capacity: int = 120,
        refill_period_seconds: int | float = 60.0,
        max_tracked_buckets: int = MAX_TRACKED_BUCKETS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not is_exact_int(capacity) or not 1 <= capacity <= MAX_BUCKET_CAPACITY:
            raise ValueError("capacity must be an integer between 1 and 1000000")
        if (
            not is_exact_number(refill_period_seconds)
            or not _finite_number(refill_period_seconds)
            or not MIN_REFILL_PERIOD_SECONDS
            <= refill_period_seconds
            <= MAX_REFILL_PERIOD_SECONDS
        ):
            raise ValueError(
                "refill period must be between 0.001 seconds and one year"
            )
        if (
            not is_exact_int(max_tracked_buckets)
            or not 1 <= max_tracked_buckets <= MAX_TRACKED_BUCKETS
        ):
            raise ValueError("tracked bucket limit must be between 1 and 10000")
        self._store = store
        self.capacity = capacity
        self.refill_period_seconds = float(refill_period_seconds)
        self.refill_rate = capacity / self.refill_period_seconds
        self.max_tracked_buckets = max_tracked_buckets
        self._clock = clock

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume a token, denying safely when the bounded table is full."""

        if not self._valid_identifier(subject_id) or not self._valid_identifier(
            project_id
        ):
            return False
        now = self._now()
        with self._store.transaction() as connection:
            row = connection.execute(
                "SELECT tokens, updated_at, touched_at FROM request_rate_buckets "
                "WHERE subject_id = ? AND project_id = ?",
                (subject_id, project_id),
            ).fetchone()
            if row is None:
                if not self._reserve_bucket(connection, now):
                    return False
                connection.execute(
                    "INSERT INTO request_rate_buckets "
                    "(subject_id, project_id, tokens, updated_at, touched_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (subject_id, project_id, float(self.capacity - 1), now, now),
                )
                return True

            previous_updated = float(row["updated_at"])
            effective_now = max(now, previous_updated)
            tokens = min(
                float(self.capacity),
                max(0.0, float(row["tokens"]))
                + (effective_now - previous_updated) * self.refill_rate,
            )
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            connection.execute(
                "UPDATE request_rate_buckets SET tokens = ?, updated_at = ?, "
                "touched_at = ? WHERE subject_id = ? AND project_id = ?",
                (
                    tokens,
                    effective_now,
                    max(now, float(row["touched_at"])),
                    subject_id,
                    project_id,
                ),
            )
            return allowed

    def _reserve_bucket(self, connection: sqlite3.Connection, now: float) -> bool:
        """Prune only fully refilled idle rows before applying the hard cap."""

        count = int(
            connection.execute("SELECT count(*) FROM request_rate_buckets").fetchone()[
                0
            ]
        )
        if count < self.max_tracked_buckets:
            return True
        idle_before = now - self.refill_period_seconds
        connection.execute(
            "DELETE FROM request_rate_buckets WHERE touched_at < ?",
            (idle_before,),
        )
        count = int(
            connection.execute("SELECT count(*) FROM request_rate_buckets").fetchone()[
                0
            ]
        )
        return count < self.max_tracked_buckets

    def _now(self) -> float:
        """Read a finite wall clock suitable for shared persisted timestamps."""

        value = self._clock()
        if not is_exact_number(value) or not _finite_number(value) or value < 0:
            raise ValueError("rate-limit clock must return a finite nonnegative number")
        return float(value)

    @staticmethod
    def _valid_identifier(value: object) -> bool:
        """Validate the bounded opaque keys before creating persistent rows."""

        return isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value) is not None


def _finite_number(value: int | float) -> bool:
    """Check numeric finiteness without overflowing on arbitrary-sized ints."""

    try:
        return math.isfinite(value)
    except OverflowError:
        return False
