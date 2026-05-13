# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
Tests for `ucon.tools.mcp.system.process_base.ProcessBase`.

Acceptance:
- frozen / hashable
- `from_globals()` yields a populated value
- `unit_system` defaults to `get_default_graph()`
- `tools` mirrors registered MCP tool roster
- `formulas` mirrors formula registry
"""
from __future__ import annotations

import pytest

from ucon.graph import ConversionGraph, get_default_graph
from ucon.tools.mcp.formulas import list_formulas
from ucon.tools.mcp.system import ProcessBase


def test_process_base_is_frozen():
    pb = ProcessBase(unit_system=get_default_graph())
    with pytest.raises(Exception):  # FrozenInstanceError subclass of AttributeError
        pb.tools = frozenset({"x"})  # type: ignore[misc]


def test_process_base_equality():
    g = get_default_graph()
    a = ProcessBase(unit_system=g, tools=frozenset({"convert"}), formulas=frozenset({"bmi"}))
    b = ProcessBase(unit_system=g, tools=frozenset({"convert"}), formulas=frozenset({"bmi"}))
    assert a == b
    # Hashability is not required: `ConversionGraph` is mutable and not
    # hashable by design; that property propagates to `ProcessBase`. The
    # frozen contract is about attribute immutability, not hash support.


def test_from_globals_populates_fields():
    pb = ProcessBase.from_globals()
    assert isinstance(pb.unit_system, ConversionGraph)
    assert isinstance(pb.tools, frozenset)
    assert isinstance(pb.formulas, frozenset)
    # At least one tool and one formula must be registered after server import.
    import ucon.tools.mcp.server  # noqa: F401  – populates mcp tool registry
    pb = ProcessBase.from_globals()
    assert len(pb.tools) > 0
    assert len(pb.formulas) > 0


def test_from_globals_tools_match_fastmcp_registry():
    import ucon.tools.mcp.server  # noqa: F401
    from ucon.tools.mcp.server import mcp

    pb = ProcessBase.from_globals()
    # `_tool_manager._tools` is FastMCP's internal map; the discovery helper
    # walks it. If FastMCP renames the attribute, the helper should be
    # adjusted; the test asserts the discovery and the registry agree.
    expected = frozenset(getattr(mcp._tool_manager, "_tools", {}).keys())
    assert pb.tools == expected


def test_from_globals_formulas_match_registry():
    pb = ProcessBase.from_globals()
    expected = frozenset(info.name for info in list_formulas())
    assert pb.formulas == expected


def test_from_globals_unit_system_default_is_default_graph():
    pb = ProcessBase.from_globals()
    # `get_default_graph()` returns the same singleton instance.
    assert pb.unit_system is get_default_graph()


def test_from_globals_accepts_overrides():
    g = ConversionGraph()
    pb = ProcessBase.from_globals(
        unit_system=g,
        tools=frozenset({"only-this"}),
        formulas=frozenset({"only-formula"}),
        catalog="sentinel",
    )
    assert pb.unit_system is g
    assert pb.tools == frozenset({"only-this"})
    assert pb.formulas == frozenset({"only-formula"})
    assert pb.catalog == "sentinel"


def test_catalog_field_optional_default_none():
    pb = ProcessBase(unit_system=get_default_graph())
    assert pb.catalog is None
