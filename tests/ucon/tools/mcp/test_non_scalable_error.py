# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Tests for the ``non_scalable_unit`` error classification.

When the ucon resolver rejects a prefix decomposition because the base
unit has opted out of scalability (``Unit.scalable=False``), the MCP
``resolve_unit`` helper must produce a structured ``ConversionError``
with ``error_type="non_scalable_unit"`` rather than the generic
``"unknown_unit"`` classification — the base symbol *is* recognized,
only the prefix attachment is at fault.

These tests pin the contract end-to-end at three layers:

1. The ``build_non_scalable_error`` builder shape.
2. The ``resolve_unit`` choke point used by every MCP tool that parses
   a unit string.
3. The user-facing ``convert`` and ``compute`` tools, to confirm the
   classification propagates through the public surface.
"""

import unittest


class TestBuildNonScalableError(unittest.TestCase):
    """The builder produces a well-formed ``ConversionError``."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon import NonScalableError, parse_unit
            from ucon.tools.mcp.suggestions import (
                ConversionError,
                build_non_scalable_error,
            )
            cls.NonScalableError = NonScalableError
            cls.parse_unit = staticmethod(parse_unit)
            cls.ConversionError = ConversionError
            cls.build_non_scalable_error = staticmethod(build_non_scalable_error)
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def _exc(self, token: str):
        try:
            self.parse_unit(token)
        except self.NonScalableError as e:
            return e
        self.fail(f"parse_unit({token!r}) did not raise NonScalableError")

    def test_error_type_is_non_scalable_unit(self):
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="from_unit"
        )
        self.assertIsInstance(err, self.ConversionError)
        self.assertEqual(err.error_type, "non_scalable_unit")

    def test_parameter_is_preserved(self):
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="initial_unit"
        )
        self.assertEqual(err.parameter, "initial_unit")

    def test_step_is_preserved_for_multistep_chains(self):
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="factors[2].numerator", step=2
        )
        self.assertEqual(err.step, 2)

    def test_likely_fix_is_the_base_name(self):
        """The mechanical correction is to drop the prefix."""
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="from_unit"
        )
        self.assertEqual(err.likely_fix, "each")

    def test_got_and_expected_fields(self):
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="from_unit"
        )
        self.assertEqual(err.got, "meach")
        self.assertEqual(err.expected, "each")

    def test_hint_explains_scalability_gate(self):
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="from_unit"
        )
        combined = " ".join(err.hints)
        self.assertIn("scalable=False", combined)

    def test_hint_names_the_prefix_to_drop(self):
        """The agent should be told which prefix to remove."""
        err = self.build_non_scalable_error(
            self._exc("meach"), parameter="from_unit"
        )
        combined = " ".join(err.hints)
        self.assertIn("'m'", combined)
        self.assertIn("each", combined)


class TestResolveUnitNonScalable(unittest.TestCase):
    """``resolve_unit`` classifies prefix-over-non-scalable as
    ``non_scalable_unit``, distinct from ``unknown_unit``."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.suggestions import resolve_unit
            cls.resolve_unit = staticmethod(resolve_unit)
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_meach_returns_non_scalable_unit(self):
        unit, err = self.resolve_unit("meach", parameter="from_unit")
        self.assertIsNone(unit)
        self.assertIsNotNone(err)
        self.assertEqual(err.error_type, "non_scalable_unit")
        self.assertEqual(err.likely_fix, "each")
        self.assertEqual(err.parameter, "from_unit")

    def test_kdB_returns_non_scalable_unit(self):
        """Decibel is logarithmic — prefix attachment is meaningless."""
        unit, err = self.resolve_unit("kdB", parameter="to_unit")
        self.assertIsNone(unit)
        self.assertIsNotNone(err)
        self.assertEqual(err.error_type, "non_scalable_unit")
        self.assertEqual(err.likely_fix, "decibel")

    def test_genuine_typo_still_unknown_unit(self):
        """Tokens with no scalable interpretation stay ``unknown_unit``."""
        unit, err = self.resolve_unit("flarble", parameter="to_unit")
        self.assertIsNone(unit)
        self.assertEqual(err.error_type, "unknown_unit")

    def test_scalable_prefix_decomposition_still_succeeds(self):
        """Regression guard: ``km``, ``Mg`` etc. must continue to parse."""
        unit, err = self.resolve_unit("km", parameter="to_unit")
        self.assertIsNone(err)
        self.assertIsNotNone(unit)

    def test_base_non_scalable_unit_itself_still_parses(self):
        """Using ``each`` directly (no prefix) must continue to work."""
        unit, err = self.resolve_unit("each", parameter="from_unit")
        self.assertIsNone(err)
        self.assertIsNotNone(unit)


class TestNonScalablePropagatesThroughConvert(unittest.TestCase):
    """The public ``convert`` tool surfaces ``non_scalable_unit``."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import convert
            from ucon.tools.mcp.suggestions import ConversionError
            cls.convert = staticmethod(convert)
            cls.ConversionError = ConversionError
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_convert_with_prefixed_non_scalable_source(self):
        result = self.convert(1, "meach", "each")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")
        self.assertEqual(result.parameter, "from_unit")
        self.assertEqual(result.likely_fix, "each")

    def test_convert_with_prefixed_non_scalable_target(self):
        result = self.convert(1, "each", "meach")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")
        self.assertEqual(result.parameter, "to_unit")


class TestNonScalablePropagatesThroughCompute(unittest.TestCase):
    """The public ``compute`` tool surfaces ``non_scalable_unit`` and
    preserves the offending ``step`` index in multi-step chains."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import compute
            from ucon.tools.mcp.suggestions import ConversionError
            cls.compute = staticmethod(compute)
            cls.ConversionError = ConversionError
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_compute_initial_unit_non_scalable(self):
        result = self.compute(
            initial_value=1,
            initial_unit="meach",
            factors=[],
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")
        self.assertEqual(result.parameter, "initial_unit")

    def test_compute_factor_numerator_non_scalable_preserves_step(self):
        result = self.compute(
            initial_value=1,
            initial_unit="m",
            factors=[
                {"value": 1, "numerator": "m", "denominator": "m"},
                {"value": 1, "numerator": "meach", "denominator": "m"},
            ],
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")
        self.assertEqual(result.step, 1)


if __name__ == "__main__":
    unittest.main()
