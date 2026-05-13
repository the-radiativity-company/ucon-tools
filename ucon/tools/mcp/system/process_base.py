# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.process_base
==================================

`ProcessBase` is the frozen value owning the per-process foundation of the
MCP server: the base unit system, the advertised tool roster, the registered
formulas, and the bundle catalog. It is built once at process startup and
referenced by `OverlayPolicy.resolve(...)` on every request.

See `docs/internal/IMPLEMENTATION_PLAN_ucon-tools-v0.5.0.md` (§2, §6) and
the seam doc `IMPLEMENTATION_PLAN_capability-bundle-composition.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ucon.graph import ConversionGraph


@dataclass(frozen=True)
class ProcessBase:
    """Per-process foundation: base unit system, tools, formulas, catalog.

    Pinned at startup. Composed bottom-up with operator overlays and (in
    STANDARD tier) session overlays via `OverlayPolicy.resolve(...)`.

    Attributes
    ----------
    unit_system : ConversionGraph
        The base conversion graph for the process. In v0.5.0 the substrate
        is ucon's `ConversionGraph` (the "active unit system" mechanism).
    tools : frozenset[str]
        Names of MCP tools advertised by this process. Dispatch gates each
        request by `request.tool in effective.tools`.
    formulas : frozenset[str]
        Names of registered domain formulas. Mirrors the formula registry
        at process-startup snapshot time.
    catalog : Any
        The `BundleCatalog` (Protocol) of known bundles. Typed as `Any` in
        v0.5.0's Step 2 to keep this module free of Step-4 dependencies;
        Step 4 ships `BundleCatalog` and `DEFAULT_CATALOG`.
    """

    unit_system: "ConversionGraph"
    tools: frozenset[str] = field(default_factory=frozenset)
    formulas: frozenset[str] = field(default_factory=frozenset)
    catalog: Any = None

    @classmethod
    def from_globals(
        cls,
        *,
        unit_system: "ConversionGraph | None" = None,
        tools: frozenset[str] | None = None,
        formulas: frozenset[str] | None = None,
        catalog: Any = None,
    ) -> "ProcessBase":
        """Build a `ProcessBase` from the legacy module-level state.

        Defaults each field by introspecting the running process:

        - `unit_system`: `ucon.graph.get_default_graph()`.
        - `tools`: names of every `@mcp.tool()` registered on the
          module-level `FastMCP` instance in `ucon.tools.mcp.server`.
        - `formulas`: names returned by the formula registry's
          `list_formulas()`.
        - `catalog`: caller-supplied (Step 4 introduces a default).

        Any explicit keyword overrides the corresponding default. The
        method has no side effects; it produces a fresh frozen value.
        """
        if unit_system is None:
            from ucon.graph import get_default_graph
            unit_system = get_default_graph()
        if tools is None:
            tools = _discover_registered_tools()
        if formulas is None:
            formulas = _discover_registered_formulas()
        return cls(
            unit_system=unit_system,
            tools=tools,
            formulas=formulas,
            catalog=catalog,
        )


def _discover_registered_tools() -> frozenset[str]:
    """Names of `@mcp.tool()`-decorated functions on the server's FastMCP.

    Walks the FastMCP tool-manager state. The tool manager's exposed
    attribute is `_tool_manager` in current `mcp.server.fastmcp`; access
    via the public listing if the private form moves.
    """
    from ucon.tools.mcp.server import mcp

    manager = getattr(mcp, "_tool_manager", None)
    if manager is None:
        return frozenset()
    tools_attr = getattr(manager, "_tools", None)
    if isinstance(tools_attr, dict):
        return frozenset(tools_attr.keys())
    return frozenset()


def _discover_registered_formulas() -> frozenset[str]:
    """Names of formulas registered via `@register_formula`."""
    from ucon.tools.mcp.formulas import list_formulas
    return frozenset(info.name for info in list_formulas())
