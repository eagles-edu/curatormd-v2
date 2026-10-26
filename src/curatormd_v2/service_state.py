"""Own service dependencies and the project effect fence."""

from __future__ import annotations

__all__ = (
    "_CuratorServiceState",
)

from collections.abc import (
    Callable,
    Generator,
)
from contextlib import (
    AbstractContextManager,
    contextmanager,
    nullcontext,
)
import re
from .evidence import (
    EvidenceVerifier,
    RejectUnverifiedEvidence,
)
from .purge import ArtifactPurger
from .reviews import (
    RejectUnauthenticatedReview,
    ReviewAuthorizer,
)
from .store import (
    ConflictError,
    CuratorStore,
    NotFoundError,
)


class _CuratorServiceState:  # pylint: disable=too-few-public-methods  # Internal mixin boundary.
    """Own service dependencies and the project effect fence."""

    def __init__(
        self,
        store: CuratorStore,
        purger: ArtifactPurger,
        evidence_verifier: EvidenceVerifier | None = None,
        review_authorizer: ReviewAuthorizer | None = None,
        *,
        project_id: str = "default",
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        self.store = store
        self.purger = purger
        self.evidence_verifier = evidence_verifier or RejectUnverifiedEvidence()
        self.review_authorizer = review_authorizer or RejectUnauthenticatedReview()
        self.project_id = project_id
        self._effect_revision_capture: Callable[[], int] | None = None
        self._effect_revision_fence: (
            Callable[[int], AbstractContextManager[object]] | None
        ) = None

    def bind_project_effect_boundary(
        self,
        capture_revision: Callable[[], int],
        revision_fence: Callable[[int], AbstractContextManager[object]],
    ) -> None:
        """Bind this service's direct mutations to a repository-owned project."""

        if self._effect_revision_capture is not None:
            raise RuntimeError("project effect boundary is already bound")
        self._effect_revision_capture = capture_revision
        self._effect_revision_fence = revision_fence

    def _capture_effect_revision(self) -> int | None:
        """Capture the bound project's active revision before an effect phase."""

        if self._effect_revision_capture is not None:
            return self._effect_revision_capture()
        try:
            registration = self.store.get_project_registration(self.project_id)
        except NotFoundError:
            # Preserve standalone/unregistered service use. Once a project is
            # registered, its lifecycle becomes authoritative for this service.
            return None
        if registration.status != "active":
            raise ConflictError("project lifecycle changed before the effect")
        return registration.revision

    def _effect_fence(
        self, expected_revision: int | None
    ) -> AbstractContextManager[object]:
        """Return the captured-revision fence, preserving unbound service use."""

        if expected_revision is None:
            return nullcontext()
        if self._effect_revision_fence is not None:
            return self._effect_revision_fence(expected_revision)
        return self.store.project_revision_fence(self.project_id, expected_revision)

    @contextmanager
    def _effect_guard(
        self,
        expected_revision: int | None,
        additional_fence: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> Generator[None, None, None]:
        """Apply the bound project fence even when a caller supplies another fence."""

        with self._effect_fence(expected_revision):
            if additional_fence is None:
                yield
            else:
                with additional_fence():
                    yield
