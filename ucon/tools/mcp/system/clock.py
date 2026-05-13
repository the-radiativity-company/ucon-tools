# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.clock
===========================

Time abstraction for the capability framework. All wall-clock reads in
v0.5.0 dispatch and activation flow through `Clock.now()` so tests can
inject `FixedClock` and production deployments use `SystemClock`.

See `IMPLEMENTATION_PLAN_tiered-capability-control.md` (§3.7).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Wall-clock source. v0.5.0 ships `now()` only; v0.5.x may add
    `monotonic()` for elapsed-time reaping that is robust under NTP step.
    """

    def now(self) -> datetime: ...


class SystemClock:
    """Production clock. Returns timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Test clock. Returns a fixed `datetime`; advanceable via `tick`."""

    def __init__(self, t: datetime) -> None:
        self._t = t

    def now(self) -> datetime:
        return self._t

    def tick(self, delta: timedelta) -> None:
        """Advance the clock by `delta`."""
        self._t = self._t + delta

    def set(self, t: datetime) -> None:
        """Set the clock to an absolute time."""
        self._t = t
