# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.overlay
=============================

`OverlayPolicy` and two implementations:

- `SessionOverlayPolicy` — STANDARD-tier. Per-session mutable overlay
  rooted on the process base.
- `OperatorOverlayPolicy` — PREVIEW-tier. Operator bundles compose;
  session-level mutation rejected.

Both produce an `EffectiveCapabilities` per request: a frozen value
joining `unit_system`, `tools`, `formulas`, and `audit` provenance.

Scope today
-----------
`CORE_BUNDLE` (the only bundle in `DEFAULT_CATALOG`) has empty
`unit_packages` and `constants`, so bundle-level *unit-system*
composition is a no-op. The policies guard against non-empty content
with `NotImplementedError` so a future bundle that tries to carry unit
packages or constants fails loudly rather than silently dropping
content. The full `_compose_unit_system`/`SystemDelta` machinery is
anticipated but not yet implemented.

What the policies do compose:

- `tools`: process-base ∪ ⋃ active_bundles.tools
- `formulas`: process-base ∪ ⋃ active_bundles.formulas
- `audit`: tuple of `(name, version)` per active bundle
- `unit_system`: session overlay's graph (STANDARD) or the process
  base (PREVIEW)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

from ucon.tools.mcp.system.value_types import (
    CapabilityBundle,
    EffectiveCapabilities,
)

if TYPE_CHECKING:
    from ucon.graph import ConversionGraph
    from ucon.tools.mcp.session import SessionState


class SessionMutationRejected(PermissionError):
    """A non-empty `SessionOverlay` was supplied to a policy that
    disallows session-level mutation (e.g., `OperatorOverlayPolicy`).
    """


@runtime_checkable
class SessionOverlay(Protocol):
    """Per-session mutable overlay consumed by `SessionOverlayPolicy`.

    `is_empty()` lets `OperatorOverlayPolicy` defensively reject any
    overlay that actually carries content. Today the overlay's
    `get_unit_system()` returns the session's mutable conversion graph
    directly; an `as_system_delta()` materialization is anticipated
    but not yet implemented.
    """

    def is_empty(self) -> bool: ...

    def get_unit_system(self) -> "ConversionGraph": ...


@runtime_checkable
class OverlayPolicy(Protocol):
    """How a request resolves its effective capability surface."""

    def resolve(
        self,
        *,
        base: "ConversionGraph",
        base_tools: frozenset[str],
        base_formulas: frozenset[str],
        active_bundles: Sequence[CapabilityBundle],
        session_overlay: SessionOverlay | None,
    ) -> EffectiveCapabilities: ...


def _reject_bundle_unit_system_content(
    active_bundles: Sequence[CapabilityBundle],
) -> None:
    """Bundles must not carry unit-system content.

    `unit_packages` and `constants` composition into a `UnitSystem`
    requires `SystemDelta` / `UnitPackage` machinery that is not yet
    implemented. `CORE_BUNDLE` satisfies this; any other bundle
    declaring content fails loudly at resolve time.
    """
    for b in active_bundles:
        if b.unit_packages or b.constants:
            raise NotImplementedError(
                f"bundle {b.name!r}@{b.version!r} carries unit-system "
                "content (unit_packages or constants); composition into "
                "the base unit system is not yet implemented"
            )


def _compose_metadata(
    active_bundles: Sequence[CapabilityBundle],
) -> tuple[frozenset[str], frozenset[str], tuple[tuple[str, str], ...]]:
    """Compute `(tools, formulas, audit)` contributions from bundles.

    Audit is ordered to mirror activation order in the caller-supplied
    sequence.
    """
    tools: frozenset[str] = frozenset()
    formulas: frozenset[str] = frozenset()
    audit: list[tuple[str, str]] = []
    for b in active_bundles:
        tools = tools | b.tools
        formulas = formulas | b.formulas
        audit.append((b.name, b.version))
    return tools, formulas, tuple(audit)


@dataclass(frozen=True)
class SessionOverlayPolicy:
    """STANDARD-tier policy: per-session mutable overlay rooted on the
    process base.

    Bundles contribute to `tools`, `formulas`, and `audit`. If a
    `session_overlay` is supplied, its `get_unit_system()` provides the
    effective unit system; otherwise the process base is used directly.
    """

    def resolve(
        self,
        *,
        base: "ConversionGraph",
        base_tools: frozenset[str],
        base_formulas: frozenset[str],
        active_bundles: Sequence[CapabilityBundle],
        session_overlay: SessionOverlay | None,
    ) -> EffectiveCapabilities:
        _reject_bundle_unit_system_content(active_bundles)
        bundle_tools, bundle_formulas, audit = _compose_metadata(active_bundles)
        unit_system = (
            session_overlay.get_unit_system()
            if session_overlay is not None
            else base
        )
        return EffectiveCapabilities(
            unit_system=unit_system,
            tools=base_tools | bundle_tools,
            formulas=base_formulas | bundle_formulas,
            audit=audit,
        )


@dataclass(frozen=True)
class OperatorOverlayPolicy:
    """PREVIEW-tier policy: session-level mutation rejected.

    Bundles contribute to `tools`, `formulas`, and `audit`. The base
    unit system is used as-is. A non-empty `session_overlay` raises
    `SessionMutationRejected`; `None` and empty overlays are accepted.
    """

    def resolve(
        self,
        *,
        base: "ConversionGraph",
        base_tools: frozenset[str],
        base_formulas: frozenset[str],
        active_bundles: Sequence[CapabilityBundle],
        session_overlay: SessionOverlay | None,
    ) -> EffectiveCapabilities:
        if session_overlay is not None and not session_overlay.is_empty():
            raise SessionMutationRejected(
                "session-level overlay is not permitted in the PREVIEW "
                "tier; mutating tools should already be gated upstream"
            )
        _reject_bundle_unit_system_content(active_bundles)
        bundle_tools, bundle_formulas, audit = _compose_metadata(active_bundles)
        return EffectiveCapabilities(
            unit_system=base,
            tools=base_tools | bundle_tools,
            formulas=base_formulas | bundle_formulas,
            audit=audit,
        )


@dataclass(frozen=True)
class SessionStateOverlay:
    """Adapter wrapping an MCP `SessionState` into the `SessionOverlay`
    Protocol.

    `is_empty()` returns `True` only if every tracked auxiliary state
    bucket is empty (constants, quantity kinds, extended bases, active
    computation). Graph-level mutation is not introspected; a fresh
    session that has only called `get_graph()` without mutation is
    reported as empty.

    `get_unit_system()` returns the session's mutable graph
    (`session.get_graph()`).
    """

    session: "SessionState"

    def is_empty(self) -> bool:
        return (
            not self.session.get_constants()
            and not self.session.get_quantity_kinds()
            and not self.session.get_extended_bases()
            and self.session.get_active_computation() is None
        )

    def get_unit_system(self) -> "ConversionGraph":
        return self.session.get_graph()
