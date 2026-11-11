"""Regression coverage for host database binding coordination."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from curatormd_v2.bindings_coordinator import coordinate
from curatormd_v2.project_access import ProjectBindingStartupError


class BindingsCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.map_path = self.root / "bindings.json"
        self.settings = self.root / "settings.json"
        self.alpha = self.root / "alpha.sqlite3"
        self.beta = self.root / "beta.sqlite3"
        for database in (self.alpha, self.beta):
            database.touch(mode=0o600)
            database.chmod(0o600)
        self.bindings = {"alpha": str(self.alpha), "beta": str(self.beta)}
        self.map_path.write_text(json.dumps({"schema_version": 1, "projects": self.bindings}))
        self.map_path.chmod(0o600)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _coordinate(self, *, apply: bool = False, replace: bool = False) -> str:
        return coordinate(self.map_path, self.settings, apply=apply, replace=replace)

    def test_check_and_apply_preserve_unrelated_jsonc_and_are_idempotent(self) -> None:
        self.settings.write_text(
            '{\n  // Owner comment\n  "editor.fontSize": 14,\n'
            '  "curatormdV2.databaseBindings": {"alpha": '
            + json.dumps(str(self.alpha))
            + '},\n  "url": "https://example.test/a//b",\n}\n',
            encoding="utf-8",
        )
        original = self.settings.read_bytes()
        self.assertEqual(self._coordinate(), "drift")
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertEqual(self._coordinate(apply=True), "updated")
        updated = self.settings.read_text(encoding="utf-8")
        self.assertIn('// Owner comment\n  "editor.fontSize": 14,', updated)
        self.assertIn('"url": "https://example.test/a//b",\n}', updated)
        self.assertIn(str(self.beta), updated)
        self.assertEqual(self._coordinate(apply=True), "in-sync")
        self.assertEqual(self.settings.read_text(encoding="utf-8"), updated)

    def test_conflicts_and_extra_projects_require_explicit_replacement(self) -> None:
        self.settings.write_text(json.dumps({
            "curatormdV2.databaseBindings": {"alpha": str(self.beta), "extra": str(self.alpha)},
            "other": True,
        }))
        original = self.settings.read_bytes()
        with self.assertRaisesRegex(ValueError, "conflict"):
            self._coordinate(apply=True)
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertEqual(self._coordinate(apply=True, replace=True), "updated")
        saved = json.loads(self.settings.read_text())
        self.assertEqual(saved["curatormdV2.databaseBindings"], self.bindings)
        self.assertTrue(saved["other"])

    def test_missing_setting_is_inserted_without_removing_comments(self) -> None:
        self.settings.write_text('{\n  // Keep this\n  "editor.tabSize": 4,\n}\n')
        self.assertEqual(self._coordinate(apply=True), "updated")
        self.assertIn('// Keep this\n  "editor.tabSize": 4,', self.settings.read_text())
        self.assertEqual(self._coordinate(), "in-sync")

    def test_comments_inside_binding_are_not_discarded(self) -> None:
        self.settings.write_text(
            '{"curatormdV2.databaseBindings": { // owner note\n "alpha": '
            + json.dumps(str(self.alpha)) + '}}'
        )
        original = self.settings.read_bytes()
        with self.assertRaisesRegex(ValueError, "contains comments"):
            self._coordinate(apply=True)
        self.assertEqual(self.settings.read_bytes(), original)

    def test_duplicate_settings_keys_and_invalid_jsonc_are_rejected(self) -> None:
        for text in ('{"a": 1, "a": 2}', '{"a": /* unfinished', '{"a": NaN}'):
            with self.subTest(text=text):
                self.settings.write_text(text)
                with self.assertRaises(ValueError):
                    self._coordinate(apply=True)
                self.assertEqual(self.settings.read_text(), text)

    def test_bom_and_windows_line_endings_are_preserved(self) -> None:
        self.settings.write_bytes(b'\xef\xbb\xbf{\r\n  "editor.tabSize": 4\r\n}\r\n')
        self.assertEqual(self._coordinate(apply=True), "updated")
        saved = self.settings.read_bytes()
        self.assertTrue(saved.startswith(b'\xef\xbb\xbf{\r\n'))
        self.assertNotIn(b'\n', saved.replace(b'\r\n', b''))
        self.assertEqual(self._coordinate(), "in-sync")

    def test_settings_symlink_is_rejected(self) -> None:
        actual = self.root / "actual.json"
        actual.write_text('{}')
        self.settings.symlink_to(actual)
        with self.assertRaises(OSError):
            self._coordinate(apply=True)
        self.assertEqual(actual.read_text(), '{}')

    def test_map_cannot_also_be_used_as_settings(self) -> None:
        original = self.map_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "different files"):
            coordinate(self.map_path, self.map_path, apply=True, replace=True)
        self.assertEqual(self.map_path.read_bytes(), original)

    def test_empty_map_and_invalid_database_are_rejected(self) -> None:
        self.settings.write_text('{}')
        self.map_path.write_text('{"schema_version": 1, "projects": {}}')
        with self.assertRaisesRegex(ValueError, "at least one"):
            self._coordinate(apply=True)
        self.map_path.write_text(json.dumps({"schema_version": 1, "projects": self.bindings}))
        os.chmod(self.beta, 0o644)
        with self.assertRaises(ProjectBindingStartupError) as raised:
            self._coordinate(apply=True)
        self.assertEqual(str(raised.exception), "project-database-file-invalid")
        self.assertEqual(self.settings.read_text(), '{}')

    def test_source_change_during_apply_aborts_before_writing(self) -> None:
        self.settings.write_text('{}')
        with patch(
            "curatormd_v2.bindings_coordinator._canonical_bindings",
            side_effect=[self.bindings, {"alpha": str(self.alpha)}],
        ):
            with self.assertRaisesRegex(ValueError, "map changed"):
                self._coordinate(apply=True)
        self.assertEqual(self.settings.read_text(), '{}')

    def test_settings_change_during_apply_is_preserved(self) -> None:
        self.settings.write_text('{}')
        from curatormd_v2 import bindings_coordinator  # pylint: disable=import-outside-toplevel

        real_read = bindings_coordinator._read_settings  # pyright: ignore[reportPrivateUsage] # pylint: disable=protected-access
        calls = 0

        def changing_read(path: Path) -> tuple[bytes, os.stat_result]:
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_text('{"editor.tabSize": 8}')
            return real_read(path)

        with patch("curatormd_v2.bindings_coordinator._read_settings", side_effect=changing_read):
            with self.assertRaisesRegex(ValueError, "settings changed"):
                self._coordinate(apply=True)
        self.assertEqual(self.settings.read_text(), '{"editor.tabSize": 8}')

    def test_changed_post_write_readback_is_not_reported_as_success(self) -> None:
        self.settings.write_text('{}')

        def interrupted_replace(path: Path, _original: bytes, _info: os.stat_result, _updated: bytes) -> None:
            path.write_text('{"editor.tabSize": 12}')

        with patch("curatormd_v2.bindings_coordinator._replace_if_unchanged", side_effect=interrupted_replace):
            with self.assertRaisesRegex(ValueError, "changed after update"):
                self._coordinate(apply=True)
        self.assertEqual(self.settings.read_text(), '{"editor.tabSize": 12}')
