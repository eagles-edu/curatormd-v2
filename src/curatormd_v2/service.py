"""Goal lifecycle, evidence gate, SDE review, and purge orchestration."""

from __future__ import annotations

from .service_events import _EventMixin
from .service_types import (
    EvidenceGateError,
    PurgeTargetStatus,
    SDEAssessmentRequest,
    _PreparedEvent,
)

__all__ = (
    "CuratorService",
    "EvidenceGateError",
    "PurgeTargetStatus",
    "SDEAssessmentRequest",
    "_PreparedEvent",
)


class CuratorService(_EventMixin):  # pylint: disable=too-few-public-methods  # Public facade inherits its complete service API.
    """Expose the established service API over the ordered behavior mixins."""
