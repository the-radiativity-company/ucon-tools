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
    "CallerIdentity",
    "CapabilityBundle",
    "EffectiveCapabilities",
    "PREVIEW",
    "ProcessBase",
    "STANDARD",
    "TIER_CONFIGS",
    "TierConfig",
]
