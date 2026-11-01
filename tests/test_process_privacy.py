"""Tests for process-level local data privacy controls."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from curatormd_v2.process_privacy import disable_core_dumps, protect_process_data


class DisableCoreDumpsTests(unittest.TestCase):
    def test_sets_both_core_dump_limits_to_zero(self) -> None:
        resource = SimpleNamespace(RLIMIT_CORE=4, setrlimit=Mock())
        with (
            patch("curatormd_v2.process_privacy.os.name", "posix"),
            patch("curatormd_v2.process_privacy.sys.platform", "darwin"),
            patch.dict("sys.modules", {"resource": resource}),
        ):
            self.assertTrue(disable_core_dumps())
        resource.setrlimit.assert_called_once_with(4, (0, 0))

    def test_fails_closed_when_limit_cannot_be_set(self) -> None:
        resource = SimpleNamespace(RLIMIT_CORE=4, setrlimit=Mock(side_effect=OSError))
        with (
            patch("curatormd_v2.process_privacy.os.name", "posix"),
            patch("curatormd_v2.process_privacy.sys.platform", "darwin"),
            patch.dict("sys.modules", {"resource": resource}),
        ):
            self.assertFalse(disable_core_dumps())

    def test_rejects_platforms_without_posix_resource_limits(self) -> None:
        with patch("curatormd_v2.process_privacy.os.name", "nt"):
            self.assertFalse(disable_core_dumps())

    def test_linux_dump_handler_is_disabled_with_prctl(self) -> None:
        prctl = Mock(return_value=0)
        libc = SimpleNamespace(prctl=prctl)
        resource = SimpleNamespace(RLIMIT_CORE=4, setrlimit=Mock())
        with (
            patch("curatormd_v2.process_privacy.sys.platform", "linux"),
            patch("curatormd_v2.process_privacy.ctypes.CDLL", return_value=libc),
            patch.dict("sys.modules", {"resource": resource}),
        ):
            self.assertTrue(disable_core_dumps())
        resource.setrlimit.assert_called_once_with(4, (0, 0))
        prctl.assert_called_once_with(4, 0, 0, 0, 0)
        self.assertEqual(prctl.argtypes[0].__name__, "c_int")
        self.assertEqual(prctl.restype.__name__, "c_int")

    def test_linux_dump_handler_failure_is_reported(self) -> None:
        libc = SimpleNamespace(prctl=Mock(return_value=-1))
        resource = SimpleNamespace(RLIMIT_CORE=4, setrlimit=Mock())
        with (
            patch("curatormd_v2.process_privacy.sys.platform", "linux"),
            patch("curatormd_v2.process_privacy.ctypes.CDLL", return_value=libc),
            patch.dict("sys.modules", {"resource": resource}),
        ):
            self.assertFalse(disable_core_dumps())


class ProtectProcessDataTests(unittest.TestCase):
    def test_applies_owner_only_file_creation_mask_after_core_protection(self) -> None:
        with (
            patch(
                "curatormd_v2.process_privacy.disable_core_dumps",
                return_value=True,
            ) as disable,
            patch(
                "curatormd_v2.process_privacy.os.umask", return_value=0o022
            ) as umask,
        ):
            self.assertTrue(protect_process_data())
        disable.assert_called_once_with()
        umask.assert_called_once_with(0o077)

    def test_fails_closed_if_core_protection_fails(self) -> None:
        with (
            patch(
                "curatormd_v2.process_privacy.disable_core_dumps",
                return_value=False,
            ),
            patch("curatormd_v2.process_privacy.os.umask") as umask,
        ):
            self.assertFalse(protect_process_data())
        umask.assert_not_called()

    def test_fails_closed_if_private_umask_cannot_be_set(self) -> None:
        with (
            patch(
                "curatormd_v2.process_privacy.disable_core_dumps",
                return_value=True,
            ),
            patch("curatormd_v2.process_privacy.os.umask", side_effect=OSError),
        ):
            self.assertFalse(protect_process_data())


if __name__ == "__main__":
    unittest.main()
