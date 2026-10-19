"""Test strict validation of Python values used at JSON boundaries."""

from enum import IntEnum
import unittest

from curatormd_v2.validation import is_exact_bool, is_exact_int


class ExactIntegerValidationTests(unittest.TestCase):
    """Keep bools and integer subclasses out of integer-only contracts."""

    def test_accepts_only_builtin_integers(self) -> None:
        self.assertTrue(is_exact_int(0))
        self.assertTrue(is_exact_int(-12))
        self.assertFalse(is_exact_int(True))
        self.assertFalse(is_exact_int(False))

    def test_rejects_integer_subclasses(self) -> None:
        class Revision(IntEnum):
            """Integer-like enum used to verify exact-type rejection."""

            CURRENT = 1

        self.assertFalse(is_exact_int(Revision.CURRENT))


class ExactBooleanValidationTests(unittest.TestCase):
    """Keep truthy impostors out of boolean-only trust claims."""

    def test_accepts_only_builtin_booleans(self) -> None:
        self.assertTrue(is_exact_bool(True))
        self.assertTrue(is_exact_bool(False))
        self.assertFalse(is_exact_bool(1))
        self.assertFalse(is_exact_bool("false"))
