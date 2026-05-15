# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Tests for ``Unit.scalable`` surfacing in MCP tool response metadata.

Two contracts:

1. ``UnitDefinitionResult.scalable`` is **always-on**. Every successful
   ``define_unit`` call returns the resolved scalability so callers can
   read back the flag they set (or confirm the default).

2. ``ConversionResult``, ``ComputeResult``, and ``DecomposeResult`` carry
   ``source_scalable`` and ``target_scalable`` only when the tool is
   called with ``include_scalability=True``. The default is ``None``
   on both fields, keeping the steady-state response compact for the
   common case where the caller doesn't need this metadata.

Semantics for the gated fields:
- Bare ``Unit`` operand → ``unit.scalable`` (``True`` or ``False``)
- Composite ``UnitProduct`` operand → ``None`` (scalability is a
  per-factor question at the leaf level)
"""

import unittest


class TestDefineUnitScalableAlwaysOn(unittest.TestCase):
    """``UnitDefinitionResult.scalable`` is populated unconditionally."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import (
                define_unit,
                reset_session,
                UnitDefinitionResult,
            )
            cls.define_unit = staticmethod(define_unit)
            cls.UnitDefinitionResult = UnitDefinitionResult
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

    def test_default_scalable_is_true(self):
        result = self.define_unit(name="widget", dimension="count")
        self.assertIsInstance(result, self.UnitDefinitionResult)
        self.assertTrue(result.success)
        self.assertTrue(result.scalable)

    def test_scalable_false_round_trips(self):
        result = self.define_unit(
            name="gadget", dimension="count", scalable=False
        )
        self.assertIsInstance(result, self.UnitDefinitionResult)
        self.assertTrue(result.success)
        self.assertFalse(result.scalable)


class TestConvertScalabilityGating(unittest.TestCase):
    """``convert`` populates scalability fields only with the flag set."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import convert, ConversionResult
            cls.convert = staticmethod(convert)
            cls.ConversionResult = ConversionResult
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_default_omits_scalability(self):
        result = self.convert(1, "m", "m")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertIsNone(result.source_scalable)
        self.assertIsNone(result.target_scalable)

    def test_include_true_with_scalable_leaf_unit(self):
        result = self.convert(1, "m", "m", include_scalability=True)
        self.assertTrue(result.source_scalable)
        self.assertTrue(result.target_scalable)

    def test_include_true_with_non_scalable_leaf_unit(self):
        result = self.convert(1, "each", "each", include_scalability=True)
        self.assertFalse(result.source_scalable)
        self.assertFalse(result.target_scalable)

    def test_include_true_with_composite_returns_none(self):
        """``UnitProduct`` operands report ``None`` — scalability is
        per-factor at the leaf, not a single top-level answer."""
        result = self.convert(1, "m/s", "m/s", include_scalability=True)
        self.assertIsNone(result.source_scalable)
        self.assertIsNone(result.target_scalable)


class TestComputeScalabilityGating(unittest.TestCase):
    """``compute`` populates scalability fields only with the flag set."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import compute, ComputeResult
            cls.compute = staticmethod(compute)
            cls.ComputeResult = ComputeResult
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_default_omits_scalability(self):
        result = self.compute(initial_value=1, initial_unit="each", factors=[])
        self.assertIsInstance(result, self.ComputeResult)
        self.assertIsNone(result.source_scalable)
        self.assertIsNone(result.target_scalable)

    def test_include_true_reflects_non_scalable_initial_unit(self):
        result = self.compute(
            initial_value=1,
            initial_unit="each",
            factors=[],
            include_scalability=True,
        )
        self.assertFalse(result.source_scalable)
        # No factors applied, so the final unit equals the initial; both
        # surfaces should agree.
        self.assertFalse(result.target_scalable)


class TestDecomposeScalabilityGating(unittest.TestCase):
    """``decompose`` populates scalability fields only with the flag set,
    in both query and structured modes."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import decompose, DecomposeResult
            cls.decompose = staticmethod(decompose)
            cls.DecomposeResult = DecomposeResult
            cls.skip_tests = False
        except ImportError:
            cls.skip_tests = True

    def setUp(self):
        if self.skip_tests:
            self.skipTest("mcp not installed")

    def test_query_mode_default_omits_scalability(self):
        result = self.decompose(query="500 mL to L")
        self.assertIsInstance(result, self.DecomposeResult)
        self.assertIsNone(result.source_scalable)
        self.assertIsNone(result.target_scalable)

    def test_structured_mode_default_omits_scalability(self):
        result = self.decompose(initial_unit="each", target_unit="each")
        self.assertIsInstance(result, self.DecomposeResult)
        self.assertIsNone(result.source_scalable)
        self.assertIsNone(result.target_scalable)

    def test_structured_mode_with_non_scalable_units(self):
        result = self.decompose(
            initial_unit="each",
            target_unit="each",
            include_scalability=True,
        )
        self.assertIsInstance(result, self.DecomposeResult)
        self.assertFalse(result.source_scalable)
        self.assertFalse(result.target_scalable)


if __name__ == "__main__":
    unittest.main()
