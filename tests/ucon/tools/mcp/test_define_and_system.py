# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Tests for the consolidated ``define`` and ``system`` tools.

Contracts:

1. Each ``define`` kind delegates to its legacy tool and returns that
   tool's result model unchanged (parity); typed errors from the
   delegate (duplicate unit, duplicate symbol, ...) pass through.
2. Missing required parameters and unknown kinds are rejected with a
   typed ``DefineError`` carrying a corrective example, before any
   delegate runs.
3. Each ``system`` action returns the same dict payload as its legacy
   tool; unknown actions return a typed error dict.
4. Every legacy constituent's docstring opens with a deprecation line
   pointing at the consolidated surface.
"""

import unittest


class DefineSystemTestCase(unittest.TestCase):
    """Shared setup: import tools, reset session around each test."""

    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            define,
            system,
            DefineError,
            UnitDefinitionResult,
            ConversionDefinitionResult,
            ConstantDefinitionResult,
            ConversionError,
            reset_session,
        )
        from ucon.tools.mcp.koq import (
            QuantityKindDefinitionResult,
            ExtendedBasisResult,
        )
        cls.define = staticmethod(define)
        cls.system = staticmethod(system)
        cls.DefineError = DefineError
        cls.UnitDefinitionResult = UnitDefinitionResult
        cls.ConversionDefinitionResult = ConversionDefinitionResult
        cls.ConstantDefinitionResult = ConstantDefinitionResult
        cls.QuantityKindDefinitionResult = QuantityKindDefinitionResult
        cls.ExtendedBasisResult = ExtendedBasisResult
        cls.ConversionError = ConversionError
        cls.reset_session = staticmethod(reset_session)

    def setUp(self):
        self.reset_session()

    def tearDown(self):
        self.reset_session()


class TestDefineDelegation(DefineSystemTestCase):
    """Each kind reaches its legacy tool and returns its result model."""

    def test_define_unit(self):
        result = self.define(
            kind="unit", name="widget", dimension="length", aliases=["wdg"]
        )
        self.assertIsInstance(result, self.UnitDefinitionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.name, "widget")
        # Success message steers to the consolidated surface, not the
        # deprecated define_conversion.
        self.assertIn('define(kind="conversion")', result.message)

    def test_define_conversion(self):
        self.define(kind="unit", name="widget", dimension="length")
        result = self.define(
            kind="conversion", src="widget", dst="meter", factor=2.5
        )
        self.assertIsInstance(result, self.ConversionDefinitionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.factor, 2.5)

    def test_define_constant(self):
        result = self.define(
            kind="constant",
            symbol="v_test",
            name="test speed",
            value=343.0,
            unit="m/s",
        )
        self.assertIsInstance(result, self.ConstantDefinitionResult)
        self.assertTrue(result.success)
        # Success message steers to discover, not the deprecated
        # list_constants.
        self.assertIn('discover(topic="constants")', result.message)

    def test_define_quantity_kind(self):
        result = self.define(
            kind="quantity_kind",
            name="test_entropy_change",
            dimension="energy/temperature",
            description="test kind",
        )
        self.assertIsInstance(result, self.QuantityKindDefinitionResult)
        self.assertTrue(result.success)

    def test_define_basis(self):
        result = self.define(
            kind="basis",
            name="test_basis",
            additional_components=[
                {"name": "thermal", "symbol": "Φ", "description": "marker"}
            ],
        )
        self.assertIsInstance(result, self.ExtendedBasisResult)

    def test_typed_errors_pass_through(self):
        result = self.define(kind="unit", name="meter", dimension="length")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "duplicate_unit")


class TestDefineValidation(DefineSystemTestCase):
    """Unknown kinds and missing parameters fail typed, before delegation."""

    def test_unknown_kind(self):
        result = self.define(kind="frobnicate", name="x")
        self.assertIsInstance(result, self.DefineError)
        self.assertEqual(result.error_type, "unknown_kind")
        self.assertEqual(result.kind, "frobnicate")
        self.assertIn("unit", result.likely_fix)

    def test_missing_parameter_unit(self):
        result = self.define(kind="unit", name="widget")
        self.assertIsInstance(result, self.DefineError)
        self.assertEqual(result.error_type, "missing_parameter")
        self.assertIn("dimension", result.error)
        self.assertIn('define(kind="unit"', result.likely_fix)

    def test_missing_parameter_conversion(self):
        result = self.define(kind="conversion", src="a", dst="b")
        self.assertIsInstance(result, self.DefineError)
        self.assertEqual(result.error_type, "missing_parameter")
        self.assertIn("factor", result.error)

    def test_missing_parameter_constant(self):
        result = self.define(kind="constant", symbol="x")
        self.assertIsInstance(result, self.DefineError)
        self.assertEqual(result.error_type, "missing_parameter")
        for param in ("name", "value", "unit"):
            self.assertIn(param, result.error)


class TestSystemActions(DefineSystemTestCase):
    """Each action returns the legacy tool's dict payload."""

    def test_restrict(self):
        result = self.system(action="restrict", dimensions=["length"])
        self.assertTrue(result["success"])
        self.assertIn("length", result["dimensions"])

    def test_restrict_unknown_dimension_passes_through(self):
        result = self.system(action="restrict", dimensions=["nonsense"])
        self.assertIn("error", result)

    def test_diff(self):
        result = self.system(action="diff")
        self.assertTrue(result["success"])
        for key in ("units", "dimensions", "conversions", "constants"):
            self.assertIn(key, result)

    def test_check_compatibility(self):
        result = self.system(action="check_compatibility")
        self.assertIn("compatible", result)

    def test_unknown_action(self):
        result = self.system(action="explode")
        self.assertEqual(result["error_type"], "unknown_action")
        self.assertIn("restrict", result["likely_fix"])


class TestConstituentDeprecations(unittest.TestCase):
    """Every legacy constituent's docstring opens with a deprecation line."""

    def test_docstrings_open_with_deprecation(self):
        from ucon.tools.mcp import server

        expectations = {
            "define_unit": 'define(kind="unit")',
            "define_conversion": 'define(kind="conversion")',
            "define_constant": 'define(kind="constant")',
            "define_quantity_kind": 'define(kind="quantity_kind")',
            "extend_basis": 'define(kind="basis")',
            "restrict_system": 'system(action="restrict")',
            "diff_systems": 'system(action="diff")',
            "check_compatibility": 'system(action="check_compatibility")',
        }
        for tool_name, replacement in expectations.items():
            doc = getattr(server, tool_name).__doc__
            first_line = doc.strip().splitlines()[0]
            self.assertTrue(
                first_line.startswith("Deprecated:"),
                f"{tool_name} docstring does not open with a deprecation line",
            )
            self.assertIn(replacement, first_line)


if __name__ == "__main__":
    unittest.main()
