"""Tests for the versioned, sanitized error contract."""

from __future__ import annotations

import unittest

from curatormd_v2.errors import APIError, APIErrorCode, RateLimitExceeded, to_api_error
from curatormd_v2.reviews import ReviewAuthorizationError
from curatormd_v2.store import (
    ConflictError,
    EventInboxCapacityError,
    EventOrderError,
    FactCapacityError,
    GoalListCapacityError,
    NotFoundError,
)


class APIErrorContractTests(unittest.TestCase):
    """Map internal failures to stable codes without leaking their details."""

    def test_domain_errors_map_to_the_versioned_public_codes(self) -> None:
        """Preserve stable public classifications across domain exceptions."""

        cases = (
            (ValueError("secret-bearing invalid input"), APIErrorCode.INVALID_REQUEST),
            (ReviewAuthorizationError("private reviewer details"), APIErrorCode.FORBIDDEN),
            (NotFoundError("internal database key"), APIErrorCode.NOT_FOUND),
            (EventOrderError("source sequence 42"), APIErrorCode.CONFLICT),
            (ConflictError("internal conflict detail"), APIErrorCode.CONFLICT),
            (FactCapacityError("project=alpha facts=secret"), APIErrorCode.CAPACITY_EXCEEDED),
            (EventInboxCapacityError("global event counts"), APIErrorCode.CAPACITY_EXCEEDED),
            (GoalListCapacityError("unpaged goal count"), APIErrorCode.CAPACITY_EXCEEDED),
            (RateLimitExceeded("subject=private"), APIErrorCode.RATE_LIMITED),
            (RuntimeError("database path and query"), APIErrorCode.INTERNAL_ERROR),
        )

        for error, expected_code in cases:
            with self.subTest(error_type=type(error).__name__):
                response = to_api_error(error)
                self.assertEqual(response.code, expected_code)
                self.assertEqual(response.schema_version, 1)
                self.assertNotIn(str(error), str(response.to_dict()))

    def test_error_envelope_has_only_the_stable_versioned_fields(self) -> None:
        """Serialize exactly the fields promised by error schema version one."""

        response = to_api_error(RuntimeError("do not expose this"))

        self.assertEqual(
            response.to_dict(),
            {
                "schema_version": 1,
                "code": "internal_error",
                "message": "The request could not be completed.",
            },
        )

    def test_error_envelope_rejects_unknown_versions_and_untrusted_messages(self) -> None:
        """Reject custom messages and unsupported schema versions."""

        with self.assertRaisesRegex(ValueError, "unsupported error schema version"):
            APIError(APIErrorCode.INTERNAL_ERROR, "The request could not be completed.", 2)
        with self.assertRaisesRegex(ValueError, "unsupported error schema version"):
            APIError(APIErrorCode.INTERNAL_ERROR, "The request could not be completed.", True)
        with self.assertRaisesRegex(ValueError, "stable public text"):
            APIError(APIErrorCode.INTERNAL_ERROR, "sensitive internal error")

    def test_error_envelope_does_not_retain_untrusted_code_or_version(self) -> None:
        """Invalid error fields must not be echoed or retained in causes."""

        with self.assertRaisesRegex(
            ValueError, "unsupported API error code"
        ) as code_error:
            APIError(
                "PRIVATE_ERROR_CODE_CANARY",  # type: ignore[arg-type]
                "The request could not be completed.",
            )
        self.assertNotIn("PRIVATE_ERROR_CODE_CANARY", str(code_error.exception))
        self.assertIsNone(code_error.exception.__cause__)
        self.assertIsNone(code_error.exception.__context__)

        with self.assertRaisesRegex(
            ValueError, "unsupported error schema version"
        ) as version_error:
            APIError(
                APIErrorCode.INTERNAL_ERROR,
                "The request could not be completed.",
                "PRIVATE_VERSION_CANARY",  # type: ignore[arg-type]
            )
        self.assertNotIn("PRIVATE_VERSION_CANARY", str(version_error.exception))
        self.assertIsNone(version_error.exception.__cause__)
        self.assertIsNone(version_error.exception.__context__)


if __name__ == "__main__":
    unittest.main()
