# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Tests for the consolidated ``discover`` tool.

Contracts:

1. Every topic returns a ``DiscoverResult`` envelope whose ``items``
   carry the same entry schema as the corresponding legacy ``list_*``
   tool (parity), with ``count == len(items)`` and applied filters
   echoed back.
2. Filters that do not apply to the requested topic are rejected with
   ``error_type == "invalid_filter"`` rather than silently ignored.
3. Typed errors from the underlying lookup (unknown dimension, unknown
   constant category) pass through unchanged.
4. Session-defined entries (units, constants, quantity kinds) are
   visible alongside built-ins.
"""

import unittest


class DiscoverTestCase(unittest.TestCase):
    """Shared setup: import tools, reset session around each test."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import (
                discover,
                DiscoverResult,
                DiscoverError,
                ConversionError,
                ConstantError,
                define_unit,
                define_constant,
                define_quantity_kind,
                list_units,
                list_scales,
                list_dimensions,
                list_constants,
                list_formulas,
                list_quantity_kinds,
                list_kind_formulas,
                list_extended_bases,
                reset_session,
            )
            cls.discover = staticmethod(discover)
            cls.DiscoverResult = DiscoverResult
            cls.DiscoverError = DiscoverError
            cls.ConversionError = ConversionError
            cls.ConstantError = ConstantError
            cls.define_unit = staticmethod(define_unit)
            cls.define_constant = staticmethod(define_constant)
            cls.define_quantity_kind = staticmethod(define_quantity_kind)
            cls.list_units = staticmethod(list_units)
            cls.list_scales = staticmethod(list_scales)
            cls.list_dimensions = staticmethod(list_dimensions)
            cls.list_constants = staticmethod(list_constants)
            cls.list_formulas = staticmethod(list_formulas)
            cls.list_quantity_kinds = staticmethod(list_quantity_kinds)
            cls.list_kind_formulas = staticmethod(list_kind_formulas)
            cls.list_extended_bases = staticmethod(list_extended_bases)
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


class TestDiscoverEnvelope(DiscoverTestCase):
    """The DiscoverResult envelope is consistent across topics."""

    def test_envelope_shape(self):
        result = self.discover(topic="scales")
        self.assertIsInstance(result, self.DiscoverResult)
        self.assertEqual(result.topic, "scales")
        self.assertEqual(result.count, len(result.items))
        self.assertEqual(result.filters, {})

    def test_filters_echoed(self):
        result = self.discover(topic="units", dimension="length")
        self.assertIsInstance(result, self.DiscoverResult)
        self.assertEqual(result.filters, {"dimension": "length"})

    def test_include_builtin_false_echoed(self):
        result = self.discover(topic="quantity_kinds", include_builtin=False)
        self.assertIsInstance(result, self.DiscoverResult)
        self.assertEqual(result.filters, {"include_builtin": "false"})


class TestDiscoverParity(DiscoverTestCase):
    """discover(topic=X) items match the legacy list_* tool output."""

    def test_units_parity(self):
        legacy = [u.model_dump() for u in self.list_units()]
        self.assertEqual(self.discover(topic="units").items, legacy)

    def test_units_dimension_filter_parity(self):
        legacy = [u.model_dump() for u in self.list_units(dimension="length")]
        result = self.discover(topic="units", dimension="length")
        self.assertEqual(result.items, legacy)
        self.assertGreater(result.count, 0)

    def test_scales_parity(self):
        legacy = [s.model_dump() for s in self.list_scales()]
        self.assertEqual(self.discover(topic="scales").items, legacy)

    def test_dimensions_parity(self):
        legacy = [{"name": n} for n in self.list_dimensions()]
        self.assertEqual(self.discover(topic="dimensions").items, legacy)

    def test_constants_parity(self):
        legacy = [c.model_dump() for c in self.list_constants()]
        self.assertEqual(self.discover(topic="constants").items, legacy)

    def test_constants_category_filter_parity(self):
        legacy = [c.model_dump() for c in self.list_constants(category="exact")]
        result = self.discover(topic="constants", category="exact")
        self.assertEqual(result.items, legacy)
        self.assertGreater(result.count, 0)

    def test_formulas_parity(self):
        legacy = [f.model_dump() for f in self.list_formulas()]
        self.assertEqual(self.discover(topic="formulas").items, legacy)

    def test_quantity_kinds_parity(self):
        legacy = self.list_quantity_kinds()
        self.assertEqual(self.discover(topic="quantity_kinds").items, legacy)

    def test_kind_formulas_parity(self):
        legacy = self.list_kind_formulas()
        self.assertEqual(self.discover(topic="kind_formulas").items, legacy)

    def test_extended_bases_parity(self):
        legacy = self.list_extended_bases()
        self.assertEqual(self.discover(topic="extended_bases").items, legacy)


class TestDiscoverSessionEntries(DiscoverTestCase):
    """Session-defined entries appear alongside built-ins."""

    def test_session_unit_visible(self):
        self.define_unit(name="slug", dimension="mass")
        names = [u["name"] for u in self.discover(topic="units", dimension="mass").items]
        self.assertIn("slug", names)

    def test_session_constant_visible(self):
        self.define_constant(symbol="v_s", name="speed of sound", value=343, unit="m/s")
        result = self.discover(topic="constants", category="session")
        self.assertEqual([c["symbol"] for c in result.items], ["v_s"])

    def test_session_kind_visible(self):
        self.define_quantity_kind(
            name="entropy_change",
            dimension="energy/temperature",
            description="Session kind",
        )
        result = self.discover(topic="quantity_kinds", include_builtin=False)
        self.assertEqual([k["name"] for k in result.items], ["entropy_change"])


class TestDiscoverErrors(DiscoverTestCase):
    """Filter and topic misuse is rejected; underlying errors pass through."""

    def test_unknown_topic(self):
        result = self.discover(topic="tools")
        self.assertIsInstance(result, self.DiscoverError)
        self.assertEqual(result.error_type, "unknown_topic")
        self.assertIn("units", result.likely_fix)

    def test_inapplicable_dimension_filter(self):
        result = self.discover(topic="scales", dimension="length")
        self.assertIsInstance(result, self.DiscoverError)
        self.assertEqual(result.error_type, "invalid_filter")
        self.assertIn("units", result.likely_fix)
        self.assertIn("quantity_kinds", result.likely_fix)

    def test_inapplicable_category_filter(self):
        result = self.discover(topic="units", category="exact")
        self.assertIsInstance(result, self.DiscoverError)
        self.assertEqual(result.error_type, "invalid_filter")

    def test_inapplicable_include_builtin(self):
        result = self.discover(topic="constants", include_builtin=False)
        self.assertIsInstance(result, self.DiscoverError)
        self.assertEqual(result.error_type, "invalid_filter")

    def test_unknown_dimension_passes_through(self):
        result = self.discover(topic="units", dimension="flavor")
        self.assertIsInstance(result, self.ConversionError)

    def test_unknown_constant_category_passes_through(self):
        result = self.discover(topic="constants", category="mythical")
        self.assertIsInstance(result, self.ConstantError)


if __name__ == "__main__":
    unittest.main()
