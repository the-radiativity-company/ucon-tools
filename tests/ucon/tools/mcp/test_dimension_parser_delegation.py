# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
Tests pinning the MCP ``_parse_dimension_to_vector`` delegation to the
core ucon ``parse_dimension`` parser.

Prior to this delegation, the MCP layer maintained its own duplicate
dimension grammar that only handled named dimensions, a hand-rolled
"compound" sub-grammar, and pure vector-notation strings. As a result,
several bare-symbol forms that the core parser accepts were rejected
at the MCP boundary:

- ``M^1`` — bare symbol with ASCII caret exponent
- ``M¹``  — bare symbol with unicode-superscript exponent
- ``L^2``, ``L^3`` — non-unit ASCII-caret exponents on bare symbols
- ``L¹``, ``L²``, ``L³`` — unicode-superscript exponents on bare symbols
- ``M*L/T^2`` — compound expression mixing bare symbols and ASCII caret

A secondary mis-parse affected ``M·L/T²`` — the vector-notation fast
path swallowed the ``/`` and ``·`` together and produced an incorrect
signature with the denominator stuck to the wrong factor.

The fix tightens the vector-notation fast-path guard to exclude
arithmetic operators and routes everything else through the core
``parse_dimension``, which already handles every shape above.
"""

import unittest


class _ParseDimensionTestBase(unittest.TestCase):
    """Shared import + skip plumbing."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import (
                _parse_dimension_to_vector,
                reset_session,
            )
            cls._parse_dimension_to_vector = staticmethod(_parse_dimension_to_vector)
            cls.reset_session = staticmethod(reset_session)
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")
        self.reset_session()

    def tearDown(self):
        if not self.skip_tests:
            self.reset_session()


class TestBareSymbolExponents(_ParseDimensionTestBase):
    """Bare component symbols with optional exponents."""

    def test_bare_M(self):
        self.assertEqual(self._parse_dimension_to_vector("M"), "M")

    def test_bare_L(self):
        self.assertEqual(self._parse_dimension_to_vector("L"), "L")

    def test_bare_T(self):
        self.assertEqual(self._parse_dimension_to_vector("T"), "T")

    def test_bare_M_caret_1(self):
        self.assertEqual(self._parse_dimension_to_vector("M^1"), "M")

    def test_bare_M_unicode_superscript_1(self):
        self.assertEqual(self._parse_dimension_to_vector("M¹"), "M")

    def test_bare_L_caret_2(self):
        self.assertEqual(self._parse_dimension_to_vector("L^2"), "L²")

    def test_bare_L_caret_3(self):
        self.assertEqual(self._parse_dimension_to_vector("L^3"), "L³")

    def test_bare_L_unicode_superscript_2(self):
        self.assertEqual(self._parse_dimension_to_vector("L²"), "L²")

    def test_bare_L_unicode_superscript_3(self):
        self.assertEqual(self._parse_dimension_to_vector("L³"), "L³")

    def test_bare_T_caret_negative_one(self):
        self.assertEqual(self._parse_dimension_to_vector("T^-1"), "T⁻¹")


class TestCompoundExpressions(_ParseDimensionTestBase):
    """Compound dimension expressions with mixed operator styles."""

    def test_compound_M_times_L_over_T_caret_2(self):
        """ASCII caret in a compound expression — force (was rejected)."""
        self.assertEqual(
            self._parse_dimension_to_vector("M*L/T^2"),
            "M·L·T⁻²",
        )

    def test_compound_M_times_L_over_T_unicode_2(self):
        """Mixed vector glyph (·, ²) with arithmetic operator (/)."""
        self.assertEqual(
            self._parse_dimension_to_vector("M·L/T²"),
            "M·L·T⁻²",
        )

    def test_compound_mass_over_time(self):
        """Named-dimension compound still works."""
        self.assertEqual(
            self._parse_dimension_to_vector("mass/time"),
            "M·T⁻¹",
        )

    def test_compound_named_with_caret(self):
        """Named tokens with ASCII caret exponent."""
        self.assertEqual(
            self._parse_dimension_to_vector("mass*length/time^2"),
            "M·L·T⁻²",
        )


class TestPureVectorNotation(_ParseDimensionTestBase):
    """Pure vector-notation strings continue to round-trip cleanly."""

    def test_canonical_energy(self):
        self.assertEqual(
            self._parse_dimension_to_vector("M·L²·T⁻²"),
            "M·L²·T⁻²",
        )

    def test_canonical_molar_energy(self):
        self.assertEqual(
            self._parse_dimension_to_vector("M·L²·T⁻²·N⁻¹"),
            "M·L²·T⁻²·N⁻¹",
        )

    def test_canonical_velocity(self):
        self.assertEqual(
            self._parse_dimension_to_vector("L·T⁻¹"),
            "L·T⁻¹",
        )


class TestDimensionless(_ParseDimensionTestBase):
    """Dimensionless inputs all collapse to the canonical ``1``."""

    def test_empty_string(self):
        self.assertEqual(self._parse_dimension_to_vector(""), "1")

    def test_whitespace_only(self):
        self.assertEqual(self._parse_dimension_to_vector("   "), "1")

    def test_word_dimensionless(self):
        self.assertEqual(self._parse_dimension_to_vector("dimensionless"), "1")

    def test_word_dimensionless_mixed_case(self):
        self.assertEqual(
            self._parse_dimension_to_vector("Dimensionless"),
            "1",
        )

    def test_literal_one(self):
        self.assertEqual(self._parse_dimension_to_vector("1"), "1")


class TestNamedDimensions(_ParseDimensionTestBase):
    """Named SI dimensions resolve to their canonical signatures."""

    def test_named_mass(self):
        self.assertEqual(self._parse_dimension_to_vector("mass"), "M")

    def test_named_length(self):
        self.assertEqual(self._parse_dimension_to_vector("length"), "L")

    def test_named_time(self):
        self.assertEqual(self._parse_dimension_to_vector("time"), "T")

    def test_named_energy(self):
        self.assertEqual(
            self._parse_dimension_to_vector("energy"),
            "M·L²·T⁻²",
        )


class TestUnknownInputs(_ParseDimensionTestBase):
    """Unrecognised dimension strings return ``None``."""

    def test_garbage_token(self):
        self.assertIsNone(self._parse_dimension_to_vector("flarble"))

    def test_unknown_symbol(self):
        self.assertIsNone(self._parse_dimension_to_vector("Q"))


if __name__ == "__main__":
    unittest.main()
