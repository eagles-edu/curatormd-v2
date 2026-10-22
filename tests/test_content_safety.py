"""Regression coverage for reject-only secret/PII validation."""

from __future__ import annotations

import unittest

from curatormd_v2.content_safety import SensitiveContentError, validate_safe_text
from curatormd_v2.events import FactRecorded
from curatormd_v2 import FactKind


class ContentSafetyTests(unittest.TestCase):
    """Sensitive inputs are rejected, never silently rewritten or echoed."""

    def test_rejects_recognized_credentials_and_personal_data(self) -> None:
        cases = (
            (
                "sde.rationale",
                "api_key=sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                "credential_assignment",
            ),
            ("fact.bullet", "Contact analyst@example.invalid for the report", "email_address"),
            ("goal.problem", "SSN 123-45-6789 was copied into the issue", "us_ssn"),
            ("fact.bullet", "phone: +1 (555) 123-4567", "labeled_phone"),
            ("evidence.locator", "https://user:pass@example.invalid/path", "credential_url"),
            ("fact.bullet", "-----BEGIN RSA PRIVATE KEY-----", "private_key"),
            ("fact.bullet", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", "provider_token"),
            ("fact.bullet", "github_pat_abcdefghijklmnopqrstuvwxyz123456", "provider_token"),
            (
                "fact.bullet",
                "ghs_1234567890_" + "A" * 480 + ".eyJhbGciOiJIUzI1NiJ9.signature",
                "provider_token",
            ),
            ("fact.bullet", "glpat-abcdefghijklmnopqrst", "provider_token"),
            ("fact.bullet", "sk" + "_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", "provider_token"),
            ("fact.bullet", "rk" + "_test_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", "provider_token"),
            (
                "fact.bullet",
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturevalue12345",
                "jwt",
            ),
        )
        for field_name, unsafe, category in cases:
            with self.subTest(category=category):
                with self.assertRaises(SensitiveContentError) as caught:
                    validate_safe_text(unsafe, field_name)
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(caught.exception.field_name, field_name)
                self.assertNotIn(unsafe, str(caught.exception))

    def test_safe_text_is_accepted_without_redaction(self) -> None:
        original = "Verified: unit checks pass; production impact remains unknown"
        self.assertIsNone(validate_safe_text(original, "fact.bullet"))
        self.assertEqual(original, "Verified: unit checks pass; production impact remains unknown")

    def test_direct_event_payloads_are_checked_not_only_json_ingress(self) -> None:
        with self.assertRaisesRegex(SensitiveContentError, "fact_recorded.bullet"):
            FactRecorded(
                "goal-1",
                "fact-1",
                FactKind.CHANGE,
                "token=synthetic-secret-value",
            )


if __name__ == "__main__":
    unittest.main()
