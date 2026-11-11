"""Exact project-to-ledger routing for local Codex MCP."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from curatormd_v2.host_database_bindings import resolve_project_database
from curatormd_v2.project_access import ProjectBindingStartupError


class HostDatabaseBindingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.chmod(self.root, 0o700)
        self.alpha = self.root / "alpha.sqlite3"
        self.vhost = self.root / "vhost.sqlite3"
        for database in (self.alpha, self.vhost):
            database.touch(mode=0o600)
            os.chmod(database, 0o600)
        self.bindings = self.root / "database-bindings.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_bindings(self, text: str) -> None:
        self.bindings.write_text(text, encoding="utf-8")
        os.chmod(self.bindings, 0o600)

    def test_routes_each_exact_project_to_its_own_database(self) -> None:
        self._write_bindings(json.dumps({
            "schema_version": 1,
            "projects": {
                "curatormd-v2-dev-alpha": str(self.alpha),
                "vhost-manager-alpha": str(self.vhost),
            },
        }))

        self.assertEqual(
            resolve_project_database("curatormd-v2-dev-alpha", self.bindings),
            self.alpha,
        )
        self.assertEqual(
            resolve_project_database("vhost-manager-alpha", self.bindings),
            self.vhost,
        )

    def test_unknown_project_fails_closed_without_shared_database_fallback(self) -> None:
        self._write_bindings(json.dumps({
            "schema_version": 1,
            "projects": {"curatormd-v2-dev-alpha": str(self.alpha)},
        }))

        with self.assertRaises(ProjectBindingStartupError) as raised:
            resolve_project_database("vhost-manager-alpha", self.bindings)

        self.assertEqual(raised.exception.code, "project-database-binding-missing")

    def test_duplicate_project_key_is_rejected(self) -> None:
        self._write_bindings(
            '{"schema_version":1,"projects":{"vhost-manager-alpha":"'
            + str(self.alpha)
            + '","vhost-manager-alpha":"'
            + str(self.vhost)
            + '"}}'
        )

        with self.assertRaises(ProjectBindingStartupError) as raised:
            resolve_project_database("vhost-manager-alpha", self.bindings)

        self.assertEqual(
            raised.exception.code, "project-database-bindings-unavailable"
        )

    def test_boolean_version_and_null_database_are_invalid_maps(self) -> None:
        documents = (
            {"schema_version": True, "projects": {"alpha": str(self.alpha)}},
            {"schema_version": 1, "projects": {"alpha": None}},
        )
        for document in documents:
            with self.subTest(document=document):
                self._write_bindings(json.dumps(document))
                with self.assertRaises(ProjectBindingStartupError) as raised:
                    resolve_project_database("alpha", self.bindings)
                self.assertEqual(
                    raised.exception.code, "project-database-bindings-unavailable"
                )

    def test_database_symlink_is_rejected(self) -> None:
        link = self.root / "linked.sqlite3"
        link.symlink_to(self.alpha)
        self._write_bindings(json.dumps({
            "schema_version": 1,
            "projects": {"curatormd-v2-dev-alpha": str(link)},
        }))

        with self.assertRaises(ProjectBindingStartupError) as raised:
            resolve_project_database("curatormd-v2-dev-alpha", self.bindings)

        self.assertEqual(raised.exception.code, "project-database-file-invalid")

    def test_group_readable_bindings_file_is_rejected(self) -> None:
        self._write_bindings(json.dumps({
            "schema_version": 1,
            "projects": {"curatormd-v2-dev-alpha": str(self.alpha)},
        }))
        os.chmod(self.bindings, 0o640)

        with self.assertRaises(ProjectBindingStartupError) as raised:
            resolve_project_database("curatormd-v2-dev-alpha", self.bindings)

        self.assertEqual(
            raised.exception.code, "project-database-bindings-unavailable"
        )
