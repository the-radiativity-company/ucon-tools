# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Behavioral regression pins for the F2 finding from the FLOPS-ergonomics
retrospective: ``define_unit(scalable=...)`` must control whether SI
prefixes attach to the resulting session unit, not just round-trip on
the response object.

``UnitDefinitionResult.scalable`` metadata round-trip is pinned in
``test_scalability_metadata.py``. The behavioral contract — that the
flag actually gates prefix decomposition in downstream ``convert`` and
``compute`` calls — is pinned here.

Two contracts:

1. ``define_unit(scalable=True)`` makes prefixed forms of the session
   unit resolve and convert with the expected SI scale factor.
2. ``define_unit(scalable=False)`` makes prefixed forms raise
   ``non_scalable_unit`` (the same classification used for built-in
   non-scalable units like ``each`` and ``decibel``), distinct from
   ``unknown_unit``.
"""

import unittest


class _SessionUnitScalabilityTestBase(unittest.TestCase):
    """Shared import + session-reset plumbing."""

    @classmethod
    def setUpClass(cls):
        try:
            from ucon.tools.mcp.server import (
                convert,
                define_unit,
                reset_session,
                ConversionResult,
            )
            from ucon.tools.mcp.suggestions import ConversionError
            cls.convert = staticmethod(convert)
            cls.define_unit = staticmethod(define_unit)
            cls.reset_session = staticmethod(reset_session)
            cls.ConversionResult = ConversionResult
            cls.ConversionError = ConversionError
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


class TestScalableSessionUnitAcceptsPrefix(_SessionUnitScalabilityTestBase):
    """``define_unit(scalable=True)`` enables SI-prefix decomposition."""

    def test_default_scalable_round_trips_through_convert(self):
        """Default is ``scalable=True``; ``Mwidget → widget`` is 1e6."""
        self.define_unit(name="widget", dimension="count")
        result = self.convert(1, "Mwidget", "widget")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertAlmostEqual(result.quantity, 1e6, places=4)

    def test_explicit_scalable_true_round_trips(self):
        self.define_unit(name="widget", dimension="count", scalable=True)
        result = self.convert(1, "kwidget", "widget")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertAlmostEqual(result.quantity, 1e3, places=4)

    def test_base_form_still_parses(self):
        """Regression guard: enabling scalability must not break the
        unprefixed base form."""
        self.define_unit(name="widget", dimension="count", scalable=True)
        result = self.convert(1, "widget", "widget")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)


class TestNonScalableSessionUnitRejectsPrefix(_SessionUnitScalabilityTestBase):
    """``define_unit(scalable=False)`` mirrors built-in non-scalable
    behaviour: prefixed forms raise ``non_scalable_unit``."""

    def test_prefixed_source_raises_non_scalable_unit(self):
        self.define_unit(name="gadget", dimension="count", scalable=False)
        result = self.convert(1, "Mgadget", "gadget")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")
        self.assertEqual(result.likely_fix, "gadget")

    def test_prefixed_target_raises_non_scalable_unit(self):
        self.define_unit(name="gadget", dimension="count", scalable=False)
        result = self.convert(1, "gadget", "kgadget")
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "non_scalable_unit")

    def test_base_form_still_parses(self):
        """A non-scalable session unit's bare form must still resolve."""
        self.define_unit(name="gadget", dimension="count", scalable=False)
        result = self.convert(1, "gadget", "gadget")
        self.assertIsInstance(result, self.ConversionResult)
        self.assertEqual(result.quantity, 1.0)


if __name__ == "__main__":
    unittest.main()
