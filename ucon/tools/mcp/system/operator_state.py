# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.operator_state
====================================

`OperatorState` — the single mutable surface in the capability framework.
Thread-safe wrapper around the active set of bundles, keyed by
`(tier, bundle.name)`. Activation, deactivation, and reaping live here;
audit emission and version-pinning policy live in the activation entry
points (Step 7) layered on top.

See `IMPLEMENTATION_PLAN_tiered-capability-control.md` (§3.4) and
`docs/internal/IMPLEMENTATION_PLAN_ucon-tools-v0.5.0.md` (§7, §8.4).
"""
from __future__ import annotations

from datetime import datetime
from threading import RLock

from ucon.tools.mcp.system.value_types import ActiveBundle


class BundleVersionMismatch(ValueError):
    """A version-pinned deactivation found a different version active."""


class OperatorState:
    """Thread-safe mutable holder for the set of activated bundles.

    Activation keys `(tier, bundle.name)` to one `ActiveBundle`; activating
    the same `(tier, name)` again overwrites the prior entry. The Step 7
    entry points layer above add eligibility checks, lease clamping, and
    audit emission; this class is intentionally policy-free.

    All public methods acquire the same `RLock`. `active_for` and
    `reap_expired` snapshot the relevant entries inside the lock and
    return immutable tuples; callers iterate without holding the lock.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._active: dict[tuple[str, str], ActiveBundle] = {}

    # ---- mutation -----------------------------------------------------

    def activate(self, active_bundle: ActiveBundle) -> None:
        """Place `active_bundle` under the `(tier, bundle.name)` key.

        Overwrites a prior entry under the same key without complaint;
        the entry-point layer is responsible for whatever conflict
        policy applies.
        """
        key = (active_bundle.tier, active_bundle.bundle.name)
        with self._lock:
            self._active[key] = active_bundle

    def deactivate(self, tier: str, name: str) -> ActiveBundle | None:
        """Remove the entry under `(tier, name)`. Idempotent.

        Returns the removed `ActiveBundle` if one was present, otherwise
        `None`. No version check; see `deactivate_versioned` for the
        pinned variant.
        """
        with self._lock:
            return self._active.pop((tier, name), None)

    def deactivate_versioned(
        self, tier: str, name: str, version: str
    ) -> ActiveBundle | None:
        """Version-pinned deactivation.

        Removes the entry under `(tier, name)` only if its bundle
        version matches `version`. Returns the removed `ActiveBundle`.
        Returns `None` if no entry is present (idempotent on inactive).
        Raises `BundleVersionMismatch` if a different version is active;
        the active set is unchanged in that case.
        """
        key = (tier, name)
        with self._lock:
            existing = self._active.get(key)
            if existing is None:
                return None
            if existing.bundle.version != version:
                raise BundleVersionMismatch(
                    f"bundle {name!r} active at version "
                    f"{existing.bundle.version!r}, requested {version!r}"
                )
            return self._active.pop(key)

    def reap_expired(self, now: datetime) -> tuple[ActiveBundle, ...]:
        """Remove and return all entries with `expires_at <= now`.

        Bundles with `expires_at is None` are indefinite and never reaped
        here. Callers (typically dispatch) emit audit records for the
        returned tuple.
        """
        with self._lock:
            expired = tuple(
                ab for ab in self._active.values()
                if ab.expires_at is not None and ab.expires_at <= now
            )
            for ab in expired:
                self._active.pop((ab.tier, ab.bundle.name), None)
            return expired

    # ---- read ---------------------------------------------------------

    def active_for(self, tier: str, now: datetime) -> tuple[ActiveBundle, ...]:
        """Snapshot of non-expired entries for `tier` at `now`.

        Read-only: does not mutate the active set. Expired bundles are
        excluded from the snapshot but remain in storage until the next
        `reap_expired` call.
        """
        with self._lock:
            return tuple(
                ab for (t, _name), ab in self._active.items()
                if t == tier and (ab.expires_at is None or ab.expires_at > now)
            )

    def snapshot(self) -> tuple[ActiveBundle, ...]:
        """All entries regardless of tier or expiry. Diagnostic only."""
        with self._lock:
            return tuple(self._active.values())
