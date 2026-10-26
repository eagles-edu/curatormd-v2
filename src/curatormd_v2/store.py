"""SQLite persistence for goals, compact facts, SDEs, and purge receipts."""

from __future__ import annotations

# Preserve the established store-module import surface for callers.
# pylint: disable=wildcard-import,unused-wildcard-import
from .store_support_01 import *
from .store_operations_14 import StoreOperations5 as _StoreOperations5

# Segment inheritance preserves the existing operation override order.
class CuratorStore(_StoreOperations5):  # pylint: disable=too-many-ancestors
    """Thread-safe SQLite store using short, explicit write transactions."""

    def __init__(self, database: str | Path) -> None:
        requested_database = str(database)
        self.database = requested_database
        if requested_database != ":memory:":
            database_path = Path(requested_database).expanduser()
            if database_path.is_symlink():
                raise ValueError("database path must not be a symlink")
            database_path = database_path.resolve()
            database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not database_path.exists():
                try:
                    descriptor = os.open(
                        database_path,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
            metadata = database_path.stat(follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("database path must be a regular file")
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise PermissionError(
                    "Curator database must be private (mode 0600 or stricter)"
                )
            self.database = str(database_path)
        self._lock = RLock()
        self._transaction_depth = 0
        self._connection = sqlite3.connect(
            self.database, isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA secure_delete = ON")
        if self.database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        try:
            self._create_schema()
            self.retry_pending_event_payload_scrubs()
        except BaseException:
            self._connection.close()
            raise


    def close(self) -> None:
        """Close the SQLite connection after its owner has finished using it."""

        with self._lock:
            self._connection.close()


    def __enter__(self) -> Self:
        """Return this store for use in a resource-managed block."""

        return self


    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the database connection when leaving a resource-managed block."""

        self.close()


    def transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        """Expose a transaction boundary for atomic multi-operation workflows."""

        return self._transaction()
