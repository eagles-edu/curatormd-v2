"""Local evidence trust config must be private, bounded, and project-bound."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import cast

from git_test_support import create_git_commit_range
from evidence_test_support import local_service_probe_config

from curatormd_v2.local_evidence_config import (
    MAX_LOCAL_EVIDENCE_CONFIG_BYTES,
    capture_local_repository_diff_reference,
    capture_local_repository_test_reference,
    load_local_browser_proof_verifier,
    load_local_evidence_verifier,
    load_local_service_probe_verifier,
)
from curatormd_v2 import BrowserProofEvidenceAdapter, EvidenceAdapterRegistry
from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.hosted_mcp import validate_host_evidence_config_path
from curatormd_v2.service_evidence import CachedLocalServiceProbeResolver


class LocalEvidenceConfigTests(unittest.TestCase):
    """Reject untrusted config files before constructing a probe verifier."""

    def setUp(self) -> None:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.temporary_directory = temporary
        self.root = Path(temporary)
        self.path = self.root / "evidence.json"
        self.value: dict[str, object] = local_service_probe_config(
            source_subject="local-probe:eaglesvn",
            command=[sys.executable, "-c", "print('ready')"],
            working_directory=str(self.root),
        )

    def _write(self, raw: bytes | None = None, *, mode: int = 0o600) -> None:
        self.path.write_bytes(raw if raw is not None else json.dumps(self.value).encode())
        self.path.chmod(mode)

    def test_accepts_owner_only_project_bound_config(self) -> None:
        self._write()

        verifier = load_local_service_probe_verifier(
            self.path, project_id="vhost-manager-alpha"
        )

        self.assertEqual(type(verifier).__name__, "ServiceProbeEvidenceAdapter")

    def test_multiple_service_probes_are_selected_by_exact_locator(self) -> None:
        original = cast(dict[str, object], self.value["probe"])
        second = dict(original)
        second.update({"probe_id": "dashboard", "adapter_id": "dashboard-adapter",
                       "command": [sys.executable, "-c", "print('dashboard-ready')"]})
        self.value["probes"] = [second]
        self._write()
        verifier = load_local_evidence_verifier(
            self.path, project_id="vhost-manager-alpha"
        )
        context = EvidenceVerificationContext(
            project_id="vhost-manager-alpha", goal_id="goal-1", criterion_id="check-1",
            now=datetime.now(UTC),
        )
        capture = getattr(verifier, "capture")
        old_id = cast(str, original["probe_id"])
        old = capture("service_probe", f"service-probe:{old_id}", context)
        first = capture("service_probe", "service-probe:dashboard", context)
        second_result = capture("service_probe", "service-probe:dashboard", context)
        self.assertIsNotNone(old)
        self.assertIsNotNone(first)
        self.assertEqual(first, second_result)
        self.assertIsNotNone(verifier.attest(first, context))
        self.assertIsNone(capture("service_probe", "service-probe:unknown", context))

    def test_duplicate_service_probe_locator_is_rejected(self) -> None:
        self.value["probes"] = [dict(cast(dict[str, object], self.value["probe"]))]
        self._write()
        with self.assertRaisesRegex(ValueError, "duplicate service probes"):
            load_local_evidence_verifier(self.path, project_id="vhost-manager-alpha")

    def test_cached_probe_receipt_is_bound_and_expires_without_rerunning(self) -> None:
        cache = self.root / "receipts"
        cache.mkdir(mode=0o700)
        probe = cast(dict[str, object], self.value["probe"])
        source = self.root / "proof.js"
        source.write_text("verified source", encoding="utf-8")
        probe.update({"cache_directory": str(cache), "cache_validity_seconds": 60,
                      "cache_integrity_files": [str(source)]})
        self._write()
        verifier = load_local_evidence_verifier(
            self.path, project_id="vhost-manager-alpha"
        )
        now = datetime.now(UTC)
        context = EvidenceVerificationContext(
            project_id="vhost-manager-alpha", goal_id="goal-1", criterion_id="check-1", now=now,
        )
        with patch.object(
            CachedLocalServiceProbeResolver, "_run_probe", return_value="a" * 64
        ) as run:
            reference = getattr(verifier, "capture")(
                "service_probe", f"service-probe:{probe['probe_id']}", context
            )
            self.assertIsNotNone(reference)
            self.assertIsNotNone(
                verifier.attest(reference, replace(context, now=now + timedelta(seconds=1)))
            )
            self.assertIsNone(verifier.attest(reference, replace(context, goal_id="other")))
            self.assertIsNone(
                verifier.attest(reference, replace(context, now=now + timedelta(seconds=61)))
            )
            run.assert_called_once()
            source.write_text("changed source", encoding="utf-8")
            self.assertIsNone(verifier.attest(reference, context))

    def test_rejects_credentials_in_child_process_arguments(self) -> None:
        marker = "alpha-process-secret-731"
        probe = cast(dict[str, object], self.value["probe"])
        for command in (
            [sys.executable, "--password", marker],
            [sys.executable, f"--api-key={marker}"],
            [sys.executable, "-c", f"api_key={marker}"],
        ):
            with self.subTest(command_shape=command[1]):
                probe["command"] = command
                self._write()
                with self.assertRaisesRegex(
                    ValueError, "private option|sensitive content"
                ) as error:
                    load_local_service_probe_verifier(
                        self.path, project_id="vhost-manager-alpha"
                    )
                self.assertNotIn(marker, str(error.exception))

        self.value = {
            "schema_version": 1,
            "project_id": "vhost-manager-alpha",
            "repository_test": {
                "adapter_id": "local-repository-test",
                "runner_id": "curator-unit-tests",
                "source_subject": "local-git:eaglesvn",
                "repository_root": str(self.root),
                "command": [sys.executable, "--token", marker],
            },
        }
        self._write()
        with self.assertRaisesRegex(ValueError, "private option") as error:
            load_local_evidence_verifier(
                self.path, project_id="vhost-manager-alpha"
            )
        self.assertNotIn(marker, str(error.exception))

    def test_loads_browser_proof_and_combined_local_sources(self) -> None:
        self.value["browser_proof"] = {
            "adapter_id": "local-browser-home",
            "proof_id": "vhost-home",
            "url": "http://127.0.0.1:8700/",
            "executable": sys.executable,
        }
        self._write()

        browser_verifier = load_local_browser_proof_verifier(
            self.path, project_id="vhost-manager-alpha"
        )
        combined_verifier = load_local_evidence_verifier(
            self.path, project_id="vhost-manager-alpha"
        )

        self.assertIsInstance(browser_verifier, BrowserProofEvidenceAdapter)
        self.assertIsInstance(combined_verifier, EvidenceAdapterRegistry)

    def test_loads_git_diff_and_test_runner_from_owner_only_config(self) -> None:
        repository, _, base_revision, head_revision = create_git_commit_range(
            self.root
        )
        self.value["repository_diff"] = {
            "adapter_id": "local-repository-diff",
            "source_subject": "local-git:eaglesvn",
            "repository_root": str(repository),
        }
        self.value["repository_test"] = {
            "adapter_id": "local-repository-test",
            "runner_id": "curator-unit-tests",
            "source_subject": "local-git:eaglesvn",
            "repository_root": str(repository),
            "command": [sys.executable, "-c", "print('bounded-test-proof')"],
        }
        self._write()

        verifier = load_local_evidence_verifier(
            self.path, project_id="vhost-manager-alpha"
        )

        self.assertIsInstance(verifier, EvidenceAdapterRegistry)
        registry = cast(EvidenceAdapterRegistry, verifier)
        self.assertEqual(
            registry.evidence_kinds,
            {"service_probe", "repository_diff", "repository_test"},
        )
        diff_reference = capture_local_repository_diff_reference(
            self.path,
            project_id="vhost-manager-alpha",
            base_revision=base_revision,
            head_revision=head_revision,
        )
        test_reference = capture_local_repository_test_reference(
            self.path,
            project_id="vhost-manager-alpha",
            runner_id="curator-unit-tests",
            commit_id=head_revision,
        )
        self.assertEqual(diff_reference.evidence_kind, "repository_diff")
        self.assertEqual(
            diff_reference.locator,
            f"git-diff:{base_revision}..{head_revision}",
        )
        self.assertEqual(test_reference.evidence_kind, "repository_test")
        self.assertEqual(
            test_reference.locator,
            f"git-test:curator-unit-tests:{head_revision}",
        )
        self.assertNotEqual(diff_reference.sha256, "0" * 64)
        self.assertNotEqual(test_reference.sha256, "0" * 64)

    def test_browser_proof_config_rejects_public_origin(self) -> None:
        self.value = {
            "schema_version": 1,
            "project_id": "vhost-manager-alpha",
            "browser_proof": {
                "adapter_id": "local-browser-home",
                "proof_id": "vhost-home",
                "url": "https://example.invalid/",
                "executable": sys.executable,
            },
        }
        self._write()

        with self.assertRaisesRegex(ValueError, "loopback host"):
            load_local_browser_proof_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

    def test_browser_proof_rejects_sensitive_url_content(self) -> None:
        marker = "browser-private-value-731"
        self.value["browser_proof"] = {
            "adapter_id": "local-browser-home",
            "proof_id": "vhost-home",
            "url": f"http://127.0.0.1/password={marker}",
            "executable": sys.executable,
        }
        self._write()

        with self.assertRaisesRegex(ValueError, "sensitive content") as error:
            load_local_browser_proof_verifier(
                self.path, project_id="vhost-manager-alpha"
            )
        self.assertNotIn(marker, str(error.exception))

    def test_rejects_group_or_world_access(self) -> None:
        self._write(mode=0o640)

        with self.assertRaisesRegex(ValueError, "ownership, mode, or size"):
            load_local_service_probe_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

    def test_rejects_duplicate_json_fields_and_wrong_project(self) -> None:
        duplicate_key = (
            b'{"schema_version":1,"schema_version":1,'
            b'"project_id":"vhost-manager-alpha","probe":{}}'
        )
        self._write(duplicate_key)
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            load_local_service_probe_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

        self._write()
        with self.assertRaisesRegex(ValueError, "does not match"):
            load_local_service_probe_verifier(self.path, project_id="other-project")

    def test_rejects_unknown_fields_and_empty_local_subject(self) -> None:
        probe = cast(dict[str, object], self.value["probe"])
        probe["extra"] = "ignored fields must not be accepted"
        self._write()
        with self.assertRaisesRegex(ValueError, "fields are invalid"):
            load_local_service_probe_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

        del probe["extra"]
        probe["source_subject"] = "local-probe:"
        self._write()
        with self.assertRaisesRegex(ValueError, "local-probe namespace"):
            load_local_service_probe_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

    def test_rejects_symlink_and_oversized_config(self) -> None:
        self._write()
        link = self.root / "evidence-link.json"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            load_local_service_probe_verifier(link, project_id="vhost-manager-alpha")

        self._write(b" " * (MAX_LOCAL_EVIDENCE_CONFIG_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "ownership, mode, or size"):
            load_local_service_probe_verifier(
                self.path, project_id="vhost-manager-alpha"
            )

    def test_host_config_must_resolve_outside_consumer_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the consumer"):
            validate_host_evidence_config_path(self.path, self.root)
        outside_link = Path(self.temporary_directory) / "host-link.json"
        outside_link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "outside the consumer"):
            validate_host_evidence_config_path(outside_link, self.root)


if __name__ == "__main__":
    unittest.main()
