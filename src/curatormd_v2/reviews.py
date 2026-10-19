"""Fail-closed review authorization boundary for human SDE decisions."""

from __future__ import annotations

from typing import Protocol

from .models import ReviewDecision


class ReviewAuthorizer(Protocol):
    """Delegate identity and project permission checks to the trusted host."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize the caller and return that reviewer's opaque subject ID."""
        ...

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize a linked correction and return its attributable reviewer."""
        ...

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize one post-disposition quality label and return its reviewer."""
        ...

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize release of an exact held artifact and return its actor."""
        ...


class RejectUnauthenticatedReview:
    """Default until Hermes Core supplies an authenticated review adapter."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Reject decisions until the trusted host provides reviewer identity."""

        del project_id, candidate_id, decision, authenticated_subject
        raise ReviewAuthorizationError("no authenticated reviewer is configured")

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Reject corrections until the trusted host provides reviewer identity."""

        del project_id, candidate_id, authenticated_subject
        raise ReviewAuthorizationError("no authenticated reviewer is configured")

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Reject feedback until the trusted host authenticates its reviewer."""

        del project_id, candidate_id, authenticated_subject
        raise ReviewAuthorizationError("no authenticated reviewer is configured")

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Reject destructive hold releases until a trusted host is supplied."""

        del project_id, receipt_id, path, rationale, authenticated_subject
        raise ReviewAuthorizationError("no authenticated reviewer is configured")


class ReviewAuthorizationError(PermissionError):
    """An SDE decision was not authorized by the configured trusted host."""
