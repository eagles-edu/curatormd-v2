"""Owner review authorization for attended local Curator hosts."""

from __future__ import annotations

import os
from pathlib import Path
import stat

from .models import ReviewDecision
from .reviews import ReviewAuthorizationError


class LocalUIDReviewAuthorizer:
    """Bind every local review action to the current non-setuid OS account."""

    # pylint: disable=too-few-public-methods

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize an SDE decision as the current local account."""

        del project_id, candidate_id, decision
        return self._subject(authenticated_subject)

    def authorize_withdrawal(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize proposal withdrawal without treating it as disposition."""

        del project_id, candidate_id
        return self._subject(authenticated_subject)

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize a correction as the current local account."""

        del project_id, candidate_id
        return self._subject(authenticated_subject)

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize post-review feedback as the current local account."""

        del project_id, candidate_id
        return self._subject(authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize one exact artifact hold release."""

        del project_id, receipt_id, path, rationale
        return self._subject(authenticated_subject)

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize one exact expired inventory."""

        del project_id, manifest_sha256
        return self._subject(authenticated_subject)

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize one exact cleanup manifest already shown to the owner."""

        del project_id, receipt_id, manifest_sha256
        return self._subject(authenticated_subject)

    def authorize_database(
        self, database: Path, authenticated_subject: str | None = None
    ) -> str:
        """Require the local reviewer to own the regular pilot database file."""

        subject = self._subject(authenticated_subject)
        metadata = database.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise ReviewAuthorizationError(
                "database must be a regular file owned by the current local account"
            )
        return subject

    @staticmethod
    def _subject(authenticated_subject: str | None) -> str:
        """Reject absent, substituted, or setuid local identity."""

        if not hasattr(os, "getuid") or not hasattr(os, "geteuid"):
            raise OSError("local UID identity is unavailable")
        if os.getuid() != os.geteuid():
            raise PermissionError("set-user-ID review is not supported")
        subject = f"local-uid:{os.geteuid()}"
        if authenticated_subject != subject:
            raise ReviewAuthorizationError(
                "local reviewer identity does not match the current OS account"
            )
        return subject
