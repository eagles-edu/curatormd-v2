"""Local evidence trust config must be private, bounded, and project-bound."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
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
from curatormd_v2.hosted_mcp import validate_host_evidence_config_path


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
