# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
Tests for `ucon.tools.mcp.system.operator_state.OperatorState`.

Acceptance (per §8.4 of the v0.5.0 plan):
- Activation places the bundle under (tier, bundle.name).
- Reap. A bundle with `expires_at <= now` is removed on
  `reap_expired(now)`; the returned tuple includes it.
- Idempotent deactivate. `deactivate(...)` on an inactive (tier, name)
  returns `None`.
- Version-pinned deactivate. `deactivate_versioned("core", "0.9")` when
  "core 1.0" is active raises `BundleVersionMismatch`; active set
  unchanged.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from ucon.tools.mcp.system import (
    ActiveBundle,
    BundleVersionMismatch,
    CapabilityBundle,
    OperatorState,
)


def _mk_active(
    name: str = "core",
    version: str = "1.0",
    tier: str = "preview",
    activated_at: datetime | None = None,
    expires_at: datetime | None = None,
    activator: str = "ops/test",
) -> ActiveBundle:
    bundle = CapabilityBundle(name=name, version=version)
    activated_at = activated_at or datetime(2026, 5, 13, tzinfo=timezone.utc)
    return ActiveBundle(
        bundle=bundle,
        tier=tier,
        activated_at=activated_at,
        expires_at=expires_at,
        activator=activator,
    )


# -----------------------------------------------------------------------------
# Activation
# -----------------------------------------------------------------------------

def test_activate_stores_under_tier_name_key():
    s = OperatorState()
    ab = _mk_active()
    s.activate(ab)
    actives = s.active_for("preview", ab.activated_at)
    assert ab in actives


def test_activate_overwrites_prior_entry_under_same_key():
    s = OperatorState()
    a = _mk_active(version="1.0")
    b = _mk_active(version="2.0")
    s.activate(a)
    s.activate(b)
    actives = s.active_for("preview", a.activated_at)
    assert actives == (b,)


def test_activate_different_tiers_coexist():
    s = OperatorState()
    a = _mk_active(tier="preview")
    b = _mk_active(tier="standard")
    s.activate(a)
    s.activate(b)
    assert s.active_for("preview", a.activated_at) == (a,)
    assert s.active_for("standard", a.activated_at) == (b,)


# -----------------------------------------------------------------------------
# Deactivation
# -----------------------------------------------------------------------------

def test_deactivate_returns_removed_entry():
    s = OperatorState()
    ab = _mk_active()
    s.activate(ab)
    removed = s.deactivate("preview", "core")
    assert removed is ab
    assert s.active_for("preview", ab.activated_at) == ()


def test_deactivate_inactive_is_idempotent_returns_none():
    s = OperatorState()
    assert s.deactivate("preview", "core") is None


def test_deactivate_versioned_matches_returns_removed_entry():
    s = OperatorState()
    ab = _mk_active(version="1.0")
    s.activate(ab)
    removed = s.deactivate_versioned("preview", "core", "1.0")
    assert removed is ab
    assert s.active_for("preview", ab.activated_at) == ()


def test_deactivate_versioned_mismatch_raises_and_preserves_active():
    s = OperatorState()
    ab = _mk_active(version="1.0")
    s.activate(ab)
    with pytest.raises(BundleVersionMismatch):
        s.deactivate_versioned("preview", "core", "0.9")
    assert s.active_for("preview", ab.activated_at) == (ab,)


def test_deactivate_versioned_inactive_is_idempotent_returns_none():
    s = OperatorState()
    assert s.deactivate_versioned("preview", "core", "1.0") is None


# -----------------------------------------------------------------------------
# Reap
# -----------------------------------------------------------------------------

def test_reap_expired_removes_and_returns_expired_entries():
    s = OperatorState()
    t0 = datetime(2026, 5, 13, tzinfo=timezone.utc)
    expired = _mk_active(name="a", expires_at=t0 + timedelta(hours=1))
    fresh = _mk_active(name="b", expires_at=t0 + timedelta(days=2))
    s.activate(expired)
    s.activate(fresh)
    now = t0 + timedelta(hours=24)
    reaped = s.reap_expired(now)
    assert reaped == (expired,)
    assert s.active_for("preview", now) == (fresh,)


def test_reap_expired_treats_none_expires_as_indefinite():
    s = OperatorState()
    t0 = datetime(2026, 5, 13, tzinfo=timezone.utc)
    ab = _mk_active(expires_at=None)
    s.activate(ab)
    reaped = s.reap_expired(t0 + timedelta(days=365 * 100))
    assert reaped == ()
    assert s.active_for("preview", t0) == (ab,)


def test_reap_at_exact_expiry_treats_as_expired():
    s = OperatorState()
    t0 = datetime(2026, 5, 13, tzinfo=timezone.utc)
    ab = _mk_active(expires_at=t0)
    s.activate(ab)
    assert s.reap_expired(t0) == (ab,)


# -----------------------------------------------------------------------------
# active_for filtering
# -----------------------------------------------------------------------------

def test_active_for_filters_expired_without_reaping():
    s = OperatorState()
    t0 = datetime(2026, 5, 13, tzinfo=timezone.utc)
    ab = _mk_active(expires_at=t0 + timedelta(hours=1))
    s.activate(ab)
    later = t0 + timedelta(hours=24)
    # Filtered out from snapshot...
    assert s.active_for("preview", later) == ()
    # ...but still in underlying state (snapshot diagnostic):
    assert ab in s.snapshot()


def test_active_for_wrong_tier_returns_empty():
    s = OperatorState()
    ab = _mk_active(tier="standard")
    s.activate(ab)
    assert s.active_for("preview", ab.activated_at) == ()


# -----------------------------------------------------------------------------
# Concurrency smoke test
# -----------------------------------------------------------------------------

def test_concurrent_activate_deactivate_no_corruption():
    s = OperatorState()
    n = 200

    def worker(i: int) -> None:
        for v in range(n):
            ab = _mk_active(name=f"b{i}", version=str(v))
            s.activate(ab)
            s.deactivate("preview", f"b{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # All entries cleared, no exceptions raised.
    assert s.snapshot() == ()
