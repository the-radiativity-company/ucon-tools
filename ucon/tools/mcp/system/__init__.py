# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system
=====================

Capability framework for v0.5.0: process base, capability bundles, tier
configuration, operator state, overlay policies.

This module is the authoritative location for the value types and runtime
state described in:

- `docs/internal/IMPLEMENTATION_PLAN_ucon-tools-v0.5.0.md`
- `IMPLEMENTATION_PLAN_capability-bundle-composition.md` (seam doc)
- `IMPLEMENTATION_PLAN_tiered-capability-control.md` (tier plan)

v0.5.0 ships incrementally; later steps extend this package.
"""
from __future__ import annotations

from ucon.tools.mcp.system.audit import (
    AuditRecord,
    AuditSink,
    CollectingSink,
    StderrJsonSink,
)
from ucon.tools.mcp.system.clock import Clock, FixedClock, SystemClock
from ucon.tools.mcp.system.catalog import (
    BundleCatalog,
    BundleNotFound,
    BundleVersionNotFound,
    CORE_BUNDLE,
    DEFAULT_CATALOG,
    StaticCatalog,
)
from ucon.tools.mcp.system.operator import (
    CapabilityTierError,
    activate_bundle,
    deactivate_bundle,
)
from ucon.tools.mcp.system.operator_state import (
    BundleVersionMismatch,
    OperatorState,
)
from ucon.tools.mcp.system.process_base import ProcessBase
from ucon.tools.mcp.system.value_types import (
    ActiveBundle,
    CallerIdentity,
    CapabilityBundle,
    EffectiveCapabilities,
    PREVIEW,
    STANDARD,
    TIER_CONFIGS,
    TierConfig,
)

__all__ = [
    "ActiveBundle",
    "AuditRecord",
    "AuditSink",
    "BundleCatalog",
    "BundleNotFound",
    "BundleVersionMismatch",
    "BundleVersionNotFound",
    "CORE_BUNDLE",
    "CallerIdentity",
    "CapabilityBundle",
    "CapabilityTierError",
    "Clock",
    "CollectingSink",
    "DEFAULT_CATALOG",
    "EffectiveCapabilities",
    "FixedClock",
    "OperatorState",
    "PREVIEW",
    "ProcessBase",
    "STANDARD",
    "StaticCatalog",
    "StderrJsonSink",
    "SystemClock",
    "TIER_CONFIGS",
    "TierConfig",
    "activate_bundle",
    "deactivate_bundle",
]
