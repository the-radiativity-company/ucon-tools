# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
Tests for `ucon.tools.mcp.system.clock`.

Acceptance:
- `SystemClock.now()` returns a timezone-aware UTC datetime.
- `FixedClock` returns the configured time and is advanceable via `tick`
  and `set`.
- Both satisfy the `Clock` Protocol at runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ucon.tools.mcp.system import Clock, FixedClock, SystemClock


def test_system_clock_returns_utc_aware_datetime():
    c = SystemClock()
    t = c.now()
    assert isinstance(t, datetime)
    assert t.tzinfo is not None
    assert t.utcoffset() == timedelta(0)


def test_system_clock_satisfies_protocol():
    assert isinstance(SystemClock(), Clock)


def test_fixed_clock_returns_configured_time():
    t0 = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    c = FixedClock(t0)
    assert c.now() == t0
    # Returns the same value on repeated calls.
    assert c.now() == t0


def test_fixed_clock_tick_advances_time():
    t0 = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    c = FixedClock(t0)
    c.tick(timedelta(hours=1))
    assert c.now() == t0 + timedelta(hours=1)
    c.tick(timedelta(minutes=30))
    assert c.now() == t0 + timedelta(hours=1, minutes=30)


def test_fixed_clock_set_jumps_to_absolute_time():
    t0 = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
    c = FixedClock(t0)
    c.set(t1)
    assert c.now() == t1


def test_fixed_clock_satisfies_protocol():
    t0 = datetime(2026, 5, 13, tzinfo=timezone.utc)
    assert isinstance(FixedClock(t0), Clock)
