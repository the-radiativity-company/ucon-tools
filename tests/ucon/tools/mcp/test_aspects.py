# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
Tests for the session aspect surface (ucon 2.2.0 adoption, #43).

Contracts:

1. ``define(kind="aspect")`` declares family roots and child positions
   for the session; structural failures return a typed
   ``AspectToolError`` and leave the session unchanged.
2. ``discover(topic="aspects")`` lists the session forest, filterable
   by family; the filter is rejected on other topics.
3. ``namespace`` qualifies declarations per D3 (ucon's
   ``rewrite_namespace``): names, parents, and ``applies_to``.
4. ``reset_session()`` clears the forest.
"""

import unittest


class AspectSurfaceTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            define,
            discover,
            reset_session,
            AspectDefinitionResult,
            AspectToolError,
        )
        cls.define = staticmethod(define)
        cls.discover = staticmethod(discover)
        cls.reset_session = staticmethod(reset_session)
        cls.AspectDefinitionResult = AspectDefinitionResult
        cls.AspectToolError = AspectToolError

    def setUp(self):
        self.reset_session()

    def tearDown(self):
        self.reset_session()

    # ---------- define ----------

    def test_define_family_root(self):
        result = self.define(
            kind="aspect", name="weighting_standard",
            applies_to=["dose_equivalent"],
        )
        self.assertIsInstance(result, self.AspectDefinitionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.family, "weighting_standard")
        self.assertIsNone(result.parent)
        self.assertEqual(result.join_policy, "refuse")   # aspect default
        self.assertEqual(result.applies_to, ["dose_equivalent"])
        self.assertEqual(result.multiplication_policy, "carry")

    def test_define_child_position(self):
        self.define(kind="aspect", name="weighting_standard")
        result = self.define(
            kind="aspect", name="icrp103", parent="weighting_standard")
        self.assertIsInstance(result, self.AspectDefinitionResult)
        self.assertEqual(result.family, "weighting_standard")
        self.assertEqual(result.parent, "weighting_standard")

    def test_define_missing_name_rejected(self):
        result = self.define(kind="aspect")
        self.assertEqual(result.error_type, "missing_parameter")

    def test_orphan_parent_is_typed_error(self):
        result = self.define(kind="aspect", name="icrp103", parent="ghost")
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")
        self.assertIn("ghost", result.likely_fix)

    def test_duplicate_name_is_typed_error(self):
        self.define(kind="aspect", name="calibrated")
        result = self.define(kind="aspect", name="calibrated")
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")

    def test_root_only_field_on_child_is_typed_error(self):
        """The forest's root-only validation surfaces as a typed error,
        and the invalid registration does not stick."""
        self.define(kind="aspect", name="weighting_standard")
        result = self.define(
            kind="aspect", name="icrp103", parent="weighting_standard",
            applies_to=["dose_equivalent"],
        )
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")
        listing = self.discover(topic="aspects")
        self.assertNotIn(
            "icrp103", [item["name"] for item in listing.items])

    def test_unrecognized_policy_is_typed_error(self):
        result = self.define(
            kind="aspect", name="x", join_policy="maybe")
        self.assertIsInstance(result, self.AspectToolError)
        self.assertIn("join_policy", result.error)

    def test_quantity_kind_join_policy_default_still_lca(self):
        """The per-kind default split leaves quantity kinds on lca."""
        result = self.define(
            kind="quantity_kind", name="probe_kind", dimension="length")
        self.assertTrue(result.success)

    # ---------- namespace (D3) ----------

    def test_namespace_qualifies_declarations(self):
        self.define(
            kind="aspect", name="weighting_standard", namespace="radsafe")
        result = self.define(
            kind="aspect", name="icrp103", parent="weighting_standard",
            namespace="radsafe",
        )
        self.assertIsInstance(result, self.AspectDefinitionResult)
        self.assertEqual(result.name, "radsafe:icrp103")
        self.assertEqual(result.family, "radsafe:weighting_standard")

    def test_qualified_spelling_passes_through(self):
        self.define(kind="aspect", name="weighting_standard",
                    namespace="radsafe")
        result = self.define(
            kind="aspect", name="icrp103",
            parent="radsafe:weighting_standard", namespace="radsafe")
        self.assertEqual(result.family, "radsafe:weighting_standard")

    # ---------- discover ----------

    def test_discover_empty_forest(self):
        result = self.discover(topic="aspects")
        self.assertEqual(result.topic, "aspects")
        self.assertEqual(result.count, 0)
        self.assertEqual(result.items, [])

    def test_discover_lists_families_roots_first(self):
        self.define(kind="aspect", name="weighting_standard",
                    applies_to=["dose_equivalent"])
        self.define(kind="aspect", name="icrp60",
                    parent="weighting_standard")
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")
        result = self.discover(topic="aspects")
        self.assertEqual(result.count, 3)
        names = [item["name"] for item in result.items]
        self.assertEqual(
            names, ["weighting_standard", "icrp103", "icrp60"])
        root = result.items[0]
        self.assertTrue(root["is_root"])
        self.assertEqual(root["applies_to"], ["dose_equivalent"])
        self.assertEqual(root["multiplication_policy"], "carry")

    def test_discover_family_filter(self):
        self.define(kind="aspect", name="weighting_standard")
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")
        self.define(kind="aspect", name="coverage", applies_to=["*"])
        result = self.discover(topic="aspects", family="weighting_standard")
        self.assertEqual(result.count, 2)
        self.assertEqual(result.filters, {"family": "weighting_standard"})

    def test_family_filter_rejected_on_other_topics(self):
        result = self.discover(topic="units", family="weighting_standard")
        self.assertEqual(result.error_type, "invalid_filter")

    # ---------- reset ----------

    def test_reset_clears_the_forest(self):
        self.define(kind="aspect", name="calibrated")
        self.reset_session()
        result = self.discover(topic="aspects")
        self.assertEqual(result.count, 0)



class ConvertAspectThreadingTestCase(unittest.TestCase):
    """Aspects on convert(): attach, thread, surface (ucon 2.2.0 carry)."""

    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            convert,
            define,
            reset_session,
            AspectToolError,
        )
        cls.convert = staticmethod(convert)
        cls.define = staticmethod(define)
        cls.reset_session = staticmethod(reset_session)
        cls.AspectToolError = AspectToolError

    def setUp(self):
        self.reset_session()

    def tearDown(self):
        self.reset_session()

    def test_aspects_thread_through_conversion(self):
        self.define(kind="aspect", name="coverage", applies_to=["*"])
        self.define(kind="aspect", name="k2", parent="coverage")
        result = self.convert(5.0, "m", "km", aspects=["k2"])
        self.assertEqual(result.quantity, 0.005)
        self.assertEqual(result.aspects, ["k2"])

    def test_no_aspects_yields_empty_list(self):
        result = self.convert(1.0, "m", "km")
        self.assertEqual(result.aspects, [])

    def test_unknown_aspect_is_typed_error(self):
        result = self.convert(5.0, "m", "km", aspects=["ghost"])
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")
        self.assertIn("ghost", result.likely_fix)

    def test_restricted_family_on_unkinded_is_not_applicable(self):
        """applies_to enforcement surfaces as a typed attachment error
        with the family named."""
        self.define(kind="aspect", name="weighting_standard",
                    applies_to=["dose_equivalent"])
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")
        result = self.convert(2.0, "m", "km", aspects=["icrp103"])
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_not_applicable")
        self.assertEqual(result.family, "weighting_standard")

    def test_kind_and_aspects_together(self):
        self.define(kind="quantity_kind", name="beam_length",
                    dimension="length")
        self.define(kind="aspect", name="calibrated")
        result = self.convert(5.0, "m", "km", kind="beam_length",
                              aspects=["calibrated"])
        self.assertEqual(result.kind, "beam_length")
        self.assertEqual(result.aspects, ["calibrated"])

    def test_restricted_family_on_wrong_kind_is_not_applicable(self):
        """A kinded measurement outside the family's applies_to is refused
        with both the family and the offending kind named."""
        self.define(kind="quantity_kind", name="beam_length",
                    dimension="length")
        self.define(kind="aspect", name="weighting_standard",
                    applies_to=["dose_equivalent"])
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")
        result = self.convert(2.0, "m", "km", kind="beam_length",
                              aspects=["icrp103"])
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_not_applicable")
        self.assertEqual(result.family, "weighting_standard")
        self.assertEqual(result.kind, "beam_length")

    def test_restricted_family_on_matching_kind_attaches(self):
        self.define(kind="aspect", name="weighting_standard",
                    applies_to=["dose_equivalent"])
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")
        result = self.convert(2.0, "Sv", "mSv", kind="dose_equivalent",
                              aspects=["icrp103"])
        self.assertEqual(result.aspects, ["icrp103"])
        self.assertEqual(result.kind, "dose_equivalent")


class ComputeAspectFoldTestCase(unittest.TestCase):
    """Aspects on compute(): the carry rule folds across the factor
    chain alongside the numeric pipeline (Law 0: resolution reads only
    the aspect sets)."""

    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            compute,
            define,
            reset_session,
            AspectToolError,
        )
        cls.compute = staticmethod(compute)
        cls.define = staticmethod(define)
        cls.reset_session = staticmethod(reset_session)
        cls.AspectToolError = AspectToolError

    def setUp(self):
        self.reset_session()
        self.define(kind="aspect", name="weighting_standard")
        self.define(kind="aspect", name="icrp60",
                    parent="weighting_standard")
        self.define(kind="aspect", name="icrp103",
                    parent="weighting_standard")

    def tearDown(self):
        self.reset_session()

    def test_initial_aspects_carry_through_the_chain(self):
        result = self.compute(
            initial_value=2.0, initial_unit="mg/kg",
            factors=[{"value": 70, "numerator": "kg", "denominator": "ea"}],
            aspects=["icrp103"],
        )
        self.assertEqual(result.quantity, 140.0)
        self.assertEqual(result.aspects, ["icrp103"])

    def test_factor_aspects_carry_onto_the_result(self):
        """Case 1c at the tool surface: an unqualified running value
        times a qualified factor — provenance rides the product."""
        result = self.compute(
            initial_value=2.0, initial_unit="mg/kg",
            factors=[{"value": 70, "numerator": "kg", "denominator": "ea",
                      "aspects": ["icrp103"]}],
        )
        self.assertEqual(result.aspects, ["icrp103"])

    def test_irreconcilable_factors_refuse_with_warrant(self):
        result = self.compute(
            initial_value=2.0, initial_unit="mg",
            factors=[
                {"value": 1, "numerator": "ea", "denominator": "ea",
                 "aspects": ["icrp60"]},
                {"value": 1, "numerator": "ea", "denominator": "ea",
                 "aspects": ["icrp103"]},
            ],
        )
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_refused")
        self.assertEqual(result.family, "weighting_standard")
        self.assertEqual(
            {result.left, result.right}, {"icrp60", "icrp103"})
        self.assertEqual(result.policy, "refuse")
        self.assertIn("step 2", result.error)

    def test_unknown_aspect_names_the_factor(self):
        result = self.compute(
            initial_value=1.0, initial_unit="mg",
            factors=[{"value": 1, "numerator": "ea", "denominator": "ea",
                      "aspects": ["ghost"]}],
        )
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")
        self.assertIn("factors[0]", result.error)

    def test_no_aspects_yields_empty_list(self):
        result = self.compute(
            initial_value=1.0, initial_unit="mg",
            factors=[{"value": 1, "numerator": "g",
                      "denominator": "1000 mg"}],
        )
        self.assertEqual(result.aspects, [])


class ValidateResultAspectTestCase(unittest.TestCase):
    """Declared aspects are checked the way declared kinds are."""

    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            define,
            reset_session,
            validate_result,
            AspectToolError,
        )
        cls.define = staticmethod(define)
        cls.reset_session = staticmethod(reset_session)
        cls.validate_result = staticmethod(validate_result)
        cls.AspectToolError = AspectToolError

    def setUp(self):
        self.reset_session()
        self.define(kind="quantity_kind", name="beam_length",
                    dimension="length")
        self.define(kind="aspect", name="calibrated")

    def tearDown(self):
        self.reset_session()

    def test_matching_aspects_pass(self):
        result = self.validate_result(
            value=5.0, unit="m", declared_kind="beam_length",
            declared_aspects=["calibrated"], aspects=["calibrated"],
        )
        self.assertTrue(result.passed)
        self.assertTrue(result.aspect_match)
        self.assertEqual(result.declared_aspects, ["calibrated"])
        self.assertEqual(result.result_aspects, ["calibrated"])

    def test_missing_aspect_fails_validation(self):
        result = self.validate_result(
            value=5.0, unit="m", declared_kind="beam_length",
            declared_aspects=["calibrated"], aspects=[],
        )
        self.assertFalse(result.passed)
        self.assertFalse(result.aspect_match)
        self.assertTrue(
            any("missing: calibrated" in w for w in result.semantic_warnings))

    def test_unexpected_aspect_fails_validation(self):
        result = self.validate_result(
            value=5.0, unit="m", declared_kind="beam_length",
            declared_aspects=[], aspects=["calibrated"],
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("unexpected: calibrated" in w
                for w in result.semantic_warnings))

    def test_undeclared_aspect_name_is_typed_error(self):
        result = self.validate_result(
            value=5.0, unit="m", declared_kind="beam_length",
            declared_aspects=["ghost"], aspects=[],
        )
        self.assertIsInstance(result, self.AspectToolError)
        self.assertEqual(result.error_type, "aspect_error")

    def test_no_aspect_params_leaves_check_unjudged(self):
        result = self.validate_result(
            value=5.0, unit="m", declared_kind="beam_length")
        self.assertIsNone(result.aspect_match)

    def test_aspect_only_call_names_the_requirement(self):
        """Regression (#47): the kind-less entry path must not steer to the
        deprecated declare_computation, and must acknowledge the aspects
        that were passed."""
        from ucon.tools.mcp.server import KOQError

        result = self.validate_result(
            value=5.0, unit="m", declared_aspects=["calibrated"])
        self.assertIsInstance(result, KOQError)
        self.assertEqual(result.error_type, "no_active_declaration")
        joined = " ".join(result.hints)
        self.assertNotIn("declare_computation", joined)
        self.assertIn("declared_aspects requires declared_kind", joined)

    def test_bare_call_hint_names_declared_kind(self):
        """Regression (#47): the hint steers to declared_kind, not the
        deprecated declare_computation."""
        from ucon.tools.mcp.server import KOQError

        result = self.validate_result(value=5.0, unit="m")
        self.assertIsInstance(result, KOQError)
        joined = " ".join(result.hints)
        self.assertNotIn("declare_computation", joined)
        self.assertIn("declared_kind", joined)


if __name__ == "__main__":
    unittest.main()
