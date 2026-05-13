# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.operator
==============================

Operator entry points for bundle activation and deactivation.

`activate_bundle` and `deactivate_bundle` are the in-process operator
surface for v0.5.0. They layer on top of `OperatorState` (Step 5) and
add:

- Catalog resolution and version pinning.
- Tier eligibility checks (`CapabilityTierError`).
- Lease computation: tier default → tier max-lease clamp → bundle
  intrinsic-expiry clamp.
- Audit emission via a caller-provided `AuditSink`.
- Forward-compat: non-empty `CapabilityBundle.restrictions` rejected
  at activation (`NotImplementedError`).

Audit emission lives here, not inside `OperatorState`, so the storage
layer stays policy-free (see §7 of the v0.5.0 plan).

See `IMPLEMENTATION_PLAN_tiered-capability-control.md` (§3.6, §4.2)
and `docs/internal/IMPLEMENTATION_PLAN_ucon-tools-v0.5.0.md` (§7, §8.4).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ucon.tools.mcp.system.audit import AuditRecord, AuditSink
from ucon.tools.mcp.system.catalog import BundleCatalog
from ucon.tools.mcp.system.operator_state import OperatorState
from ucon.tools.mcp.system.value_types import (
    ActiveBundle,
    CapabilityBundle,
    TierConfig,
)


class CapabilityTierError(PermissionError):
    """The requested bundle is not eligible under the given tier."""


def _resolve_lease(
    tier: TierConfig,
    bundle: CapabilityBundle,
    requested_lease: timedelta | None,
    now: datetime,
) -> tuple[datetime | None, datetime | None]:
    """Resolve `(expires_at, lease_clamped_from)` for an activation.

    Order of clamping:

    1. Use `requested_lease` if provided; else fall back to
       `tier.default_lease`. If both are `None`, the lease is
       indefinite (subject only to `bundle.expires_at`).
    2. Clamp the resulting `expires_at` to `now + tier.max_lease` when
       `tier.max_lease` is set and the lease exceeds it.
    3. Clamp the resulting `expires_at` to `bundle.expires_at` when the
       bundle carries an intrinsic expiry earlier than the current
       lease.

    `lease_clamped_from` is the *original* requested expiry recorded
    when any clamping occurred; `None` otherwise.
    """
    lease = requested_lease if requested_lease is not None else tier.default_lease

    if lease is None:
        # Indefinite lease: only bundle.expires_at may apply, and it is
        # not a clamp of an operator-requested lease.
        return bundle.expires_at, None

    expires_at = now + lease
    original_expires_at = expires_at
    lease_clamped_from: datetime | None = None

    if tier.max_lease is not None and lease > tier.max_lease:
        lease_clamped_from = original_expires_at
        expires_at = now + tier.max_lease

    if bundle.expires_at is not None and bundle.expires_at < expires_at:
        if lease_clamped_from is None:
            lease_clamped_from = original_expires_at
        expires_at = bundle.expires_at

    return expires_at, lease_clamped_from


def activate_bundle(
    *,
    operator_state: OperatorState,
    catalog: BundleCatalog,
    tier_config: TierConfig,
    bundle_name: str,
    bundle_version: str,
    activator: str,
    now: datetime,
    sink: AuditSink,
    requested_lease: timedelta | None = None,
) -> ActiveBundle:
    """Activate `(bundle_name, bundle_version)` under `tier_config`.

    Resolves the bundle from `catalog`, validates tier eligibility,
    computes the lease (tier-default / max-lease / bundle-expiry
    clamps), records it in `operator_state`, and emits an
    `"activate"` (or `"clamp"`-flagged) `AuditRecord` to `sink`.

    Returns the created `ActiveBundle`.

    Raises
    ------
    BundleNotFound
        Name unknown to `catalog`.
    BundleVersionNotFound
        Name known, version not.
    CapabilityTierError
        Bundle not in `tier_config.eligible_bundles`.
    NotImplementedError
        Bundle declares non-empty `restrictions` (v2-anticipation
        field; inert until later releases support enforcement).
    """
    bundle = catalog.get(bundle_name, bundle_version)

    if bundle.restrictions:
        raise NotImplementedError(
            f"bundle {bundle_name!r}@{bundle_version!r} declares "
            f"restrictions {bundle.restrictions!r}; restriction "
            "enforcement is deferred past v0.5.0"
        )

    if (
        tier_config.eligible_bundles is not None
        and bundle_name not in tier_config.eligible_bundles
    ):
        raise CapabilityTierError(
            f"bundle {bundle_name!r} not eligible under tier "
            f"{tier_config.name!r}"
        )

    expires_at, lease_clamped_from = _resolve_lease(
        tier_config, bundle, requested_lease, now
    )

    active_bundle = ActiveBundle(
        bundle=bundle,
        tier=tier_config.name,
        activated_at=now,
        expires_at=expires_at,
        activator=activator,
        lease_clamped_from=lease_clamped_from,
    )
    operator_state.activate(active_bundle)

    sink.emit(
        AuditRecord(
            event="activate",
            tier=tier_config.name,
            bundle_name=bundle.name,
            bundle_version=bundle.version,
            bundle_provenance=bundle.provenance,
            activator=activator,
            timestamp=now,
            expires_at=expires_at,
            lease_clamped_from=lease_clamped_from,
        )
    )

    return active_bundle


def deactivate_bundle(
    *,
    operator_state: OperatorState,
    tier_config: TierConfig,
    bundle_name: str,
    activator: str,
    now: datetime,
    sink: AuditSink,
    bundle_version: str | None = None,
) -> ActiveBundle | None:
    """Deactivate `(tier_config.name, bundle_name)`.

    If `bundle_version` is supplied, the deactivation is version-pinned:
    a mismatch raises `BundleVersionMismatch` (from
    `OperatorState.deactivate_versioned`) and the active set is
    unchanged.

    Returns the removed `ActiveBundle`, or `None` if no entry was
    present (idempotent no-op). Emits a `"deactivate"` audit record on
    successful removal; no record is emitted on the no-op path.
    """
    if bundle_version is None:
        removed = operator_state.deactivate(tier_config.name, bundle_name)
    else:
        removed = operator_state.deactivate_versioned(
            tier_config.name, bundle_name, bundle_version
        )

    if removed is None:
        return None

    sink.emit(
        AuditRecord(
            event="deactivate",
            tier=tier_config.name,
            bundle_name=removed.bundle.name,
            bundle_version=removed.bundle.version,
            bundle_provenance=removed.bundle.provenance,
            activator=activator,
            timestamp=now,
            expires_at=removed.expires_at,
            lease_clamped_from=removed.lease_clamped_from,
        )
    )

    return removed
