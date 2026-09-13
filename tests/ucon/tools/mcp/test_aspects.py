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


if __name__ == "__main__":
    unittest.main()
