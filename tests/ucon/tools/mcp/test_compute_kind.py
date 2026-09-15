# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Tests for `kind` threading through ``compute`` (#48).

Contracts:

1. Kinds fold through the lattice join alongside the numeric pipeline:
   the initial quantity may carry one, each factor may carry one, and
   differing kinds resolve to their lowest common ancestor.
2. A join the ancestor refuses returns a typed ``join_refused`` error
   localized to the step; kinds from disjoint trees return
   ``disjoint_kinds``.
3. Omitting kinds leaves ``compute`` exactly as it was.

Before this, no tool on the surface combined two kinds, so lattice-join
behavior was unobservable from the wire — it could only be inferred from
declared ``join_policy`` fields. That inference was made and was wrong
(ucon#304, closed as not-a-bug). These tests exercise the real thing.
"""

import unittest


class ComputeKindTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            ComputeResult,
            compute,
            define,
            reset_session,
        )
        from ucon.tools.mcp.suggestions import ConversionError

        cls.compute = staticmethod(compute)
        cls.define = staticmethod(define)
        cls.reset_session = staticmethod(reset_session)
        cls.ComputeResult = ComputeResult
        cls.ConversionError = ConversionError

    def setUp(self):
        self.reset_session()

    def tearDown(self):
        self.reset_session()

    def _times_one(self, unit="m", **extra):
        factor = {"value": 1, "numerator": unit, "denominator": "1"}
        factor.update(extra)
        return [factor]


class TestKindCarriage(ComputeKindTestCase):
    def test_no_kind_yields_none(self):
        result = self.compute(
            initial_value=2, initial_unit="m", factors=self._times_one()
        )
        self.assertIsInstance(result, self.ComputeResult)
        self.assertIsNone(result.kind)

    def test_initial_kind_carries_to_the_result(self):
        self.define(kind="quantity_kind", name="beam_len", dimension="length")
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(),
            kind="beam_len",
        )
        self.assertEqual(result.kind, "beam_len")

    def test_factor_kind_carries_when_initial_has_none(self):
        self.define(kind="quantity_kind", name="beam_len", dimension="length")
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="beam_len"),
        )
        self.assertEqual(result.kind, "beam_len")

    def test_identical_kinds_join_to_themselves(self):
        self.define(kind="quantity_kind", name="beam_len", dimension="length")
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="beam_len"),
            kind="beam_len",
        )
        self.assertEqual(result.kind, "beam_len")

    def test_siblings_join_to_their_common_ancestor(self):
        """Default `join_policy="lca"` lifts differing kinds to the LCA."""
        self.define(kind="quantity_kind", name="span", dimension="length")
        self.define(
            kind="quantity_kind", name="span_a", dimension="length", parent="span"
        )
        self.define(
            kind="quantity_kind", name="span_b", dimension="length", parent="span"
        )
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="span_b"),
            kind="span_a",
        )
        self.assertIsInstance(result, self.ComputeResult)
        self.assertEqual(result.kind, "span")


class TestKindRefusal(ComputeKindTestCase):
    """The paths that were unreachable from the wire before #48."""

    def test_refuse_root_blocks_a_sibling_join(self):
        """The builtin dose tree: `specific_energy` declares refuse."""
        result = self.compute(
            initial_value=1,
            initial_unit="Gy",
            factors=[{
                "value": 1, "numerator": "Sv", "denominator": "Gy",
                "kind": "dose_equivalent",
            }],
            kind="absorbed_dose",
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "join_refused")
        self.assertIn("absorbed_dose", result.error)
        self.assertIn("dose_equivalent", result.error)
        self.assertIn("step 1", result.error)

    def test_session_refuse_root_blocks_its_children(self):
        self.define(
            kind="quantity_kind", name="currency", dimension="length",
            join_policy="refuse",
        )
        self.define(
            kind="quantity_kind", name="c_a", dimension="length", parent="currency"
        )
        self.define(
            kind="quantity_kind", name="c_b", dimension="length", parent="currency"
        )
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="c_b"),
            kind="c_a",
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "join_refused")

    def test_disjoint_trees_are_typed(self):
        self.define(kind="quantity_kind", name="tree_a", dimension="length")
        self.define(kind="quantity_kind", name="tree_b", dimension="length")
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="tree_b"),
            kind="tree_a",
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "disjoint_kinds")
        self.assertEqual(result.step, 0)

    def test_unknown_initial_kind_is_typed(self):
        result = self.compute(
            initial_value=2, initial_unit="m", factors=self._times_one(), kind="ghost"
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "unknown_kind")
        self.assertIn("initial quantity", result.error)

    def test_unknown_factor_kind_names_the_factor(self):
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(kind="ghost"),
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "unknown_kind")
        self.assertIn("factors[0]", result.error)


class TestKindAndAspectsCoexist(ComputeKindTestCase):
    """Two strata, folded independently in one pass."""

    def test_both_thread_through_together(self):
        self.define(kind="quantity_kind", name="beam_len", dimension="length")
        self.define(kind="aspect", name="calibrated")
        result = self.compute(
            initial_value=2,
            initial_unit="m",
            factors=self._times_one(),
            kind="beam_len",
            aspects=["calibrated"],
        )
        self.assertEqual(result.kind, "beam_len")
        self.assertEqual(result.aspects, ["calibrated"])

    def test_a_kind_refusal_does_not_depend_on_aspects(self):
        self.define(kind="aspect", name="calibrated")
        result = self.compute(
            initial_value=1,
            initial_unit="Gy",
            factors=[{
                "value": 1, "numerator": "Sv", "denominator": "Gy",
                "kind": "dose_equivalent",
            }],
            kind="absorbed_dose",
            aspects=["calibrated"],
        )
        self.assertIsInstance(result, self.ConversionError)
        self.assertEqual(result.error_type, "join_refused")


if __name__ == "__main__":
    unittest.main()
