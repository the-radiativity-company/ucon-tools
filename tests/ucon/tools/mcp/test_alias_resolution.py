# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Regression pins for the F1 alias-resolution finding from the
``ucon-1.8.2-status-report``.

Prior to ucon's plural / scaled-alias work, the MCP ``convert`` tool
would return ``unknown_unit`` for several aliases that ``list_units``
advertised as registered — most visibly the ``flop`` family:

    list_units(dimension="count")
      → {"name": "flop", "aliases": ["FLOP", "flops", "FLOPs"], ...}

    convert(1, "flops", "flop")
      → {"error": "Unknown unit: 'flops'",
         "error_type": "unknown_unit",
         "hints": ["Similar units: fluid_ounce (floz), furlong (fur)", ...]}

The fuzzy matcher returned ``fluid_ounce`` / ``furlong`` rather than
recognizing ``flops`` as a registered alias of ``flop``. The fix lives
in ucon's resolver — these tests pin the public-facing contract on the
MCP surface so a regression in either layer is caught.
"""

import unittest


class TestF1AliasResolution(unittest.TestCase):
    """``convert`` resolves every advertised alias to the canonical unit."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import convert, ConversionResult
            from ucon.tools.mcp.suggestions import ConversionError
            cls.convert = staticmethod(convert)
            cls.ConversionResult = ConversionResult
            cls.ConversionError = ConversionError
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    # -- The exact F1 reproducer ---------------------------------------------

    def test_flops_to_flop_is_identity(self):
        """The reported failure: ``convert(1, "flops", "flop")``."""
        result = self.convert(1, "flops", "flop")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)
        self.assertEqual(result.unit, "flop")

    def test_FLOP_to_flop_is_identity(self):
        result = self.convert(1, "FLOP", "flop")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)

    def test_FLOPs_to_flop_is_identity(self):
        result = self.convert(1, "FLOPs", "flop")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)

    # -- Other multi-aliased units the report flagged for audit --------------

    def test_grams_to_gram_is_identity(self):
        result = self.convert(1, "grams", "gram")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)

    def test_amu_to_Da_is_identity(self):
        """``amu`` and ``Da`` are both aliases of ``dalton``."""
        result = self.convert(1, "amu", "Da")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)

    def test_amperes_to_amp_is_identity(self):
        result = self.convert(1, "amperes", "amp")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)

    # -- Regression guard: a genuinely unknown token still misses cleanly ----

    def test_genuine_typo_still_unknown_unit(self):
        """Tokens with no registered interpretation must still raise
        ``unknown_unit`` — the alias-table walk must not over-match."""
        result = self.convert(1, "flarble", "flop")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "unknown_unit")


if __name__ == "__main__":
    unittest.main()
