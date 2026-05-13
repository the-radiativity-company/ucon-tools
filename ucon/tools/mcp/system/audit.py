# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.audit
===========================

`AuditRecord` — the structured event emitted by the operator entry points
(`activate_bundle`, `deactivate_bundle`) and the dispatch reaper
(`reap_expired`).

`AuditSink` — the destination Protocol. v0.5.0 ships `StderrJsonSink`
(synchronous, JSON-line). v0.5.x will ship a bounded-queue variant.

Distinct from `EffectiveCapabilities.audit` (seam-doc provenance tuple
attached to a composed value): `AuditSink` emits operator-lifecycle
events; `EffectiveCapabilities.audit` is the per-request provenance
trail used by error formatting and introspection.

See `IMPLEMENTATION_PLAN_tiered-capability-control.md` (§3.6, §4.2) and
`docs/internal/IMPLEMENTATION_PLAN_ucon-tools-v0.5.0.md` (§8.7).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, TextIO, runtime_checkable


AuditEvent = Literal["activate", "deactivate", "clamp", "expire"]


@dataclass(frozen=True)
class AuditRecord:
    """Operator-lifecycle event.

    Attributes
    ----------
    event : {"activate", "deactivate", "clamp", "expire"}
        The lifecycle event being recorded.
    tier : str
        The tier the activation belongs to.
    bundle_name : str
    bundle_version : str
    bundle_provenance : str
        From `CapabilityBundle.provenance`. Carried in the record so the
        audit stream is self-describing without joining against the
        catalog.
    activator : str
        Identifier of the actor that triggered the event. For `"expire"`
        records emitted by dispatch reaping, the activator carried is
        the original activator of the now-expired bundle.
    timestamp : datetime
        When the event happened, per `Clock.now()`.
    expires_at : datetime | None
        Bundle expiry at the time of the event.
    lease_clamped_from : datetime | None
        Set on `"clamp"` records (and propagated on `"activate"` records
        when the activation lease was clamped); the original requested
        expiry before clamping.
    """

    event: AuditEvent
    tier: str
    bundle_name: str
    bundle_version: str
    bundle_provenance: str
    activator: str
    timestamp: datetime
    expires_at: datetime | None = None
    lease_clamped_from: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly mapping. Datetimes serialized as ISO 8601."""
        return {
            "event": self.event,
            "tier": self.tier,
            "bundle_name": self.bundle_name,
            "bundle_version": self.bundle_version,
            "bundle_provenance": self.bundle_provenance,
            "activator": self.activator,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "lease_clamped_from": (
                self.lease_clamped_from.isoformat()
                if self.lease_clamped_from else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditRecord":
        """Inverse of `to_dict`. ISO 8601 strings parsed to datetimes."""
        def _parse(v: Any) -> datetime | None:
            if v is None:
                return None
            return datetime.fromisoformat(v)

        return cls(
            event=data["event"],
            tier=data["tier"],
            bundle_name=data["bundle_name"],
            bundle_version=data["bundle_version"],
            bundle_provenance=data["bundle_provenance"],
            activator=data["activator"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            expires_at=_parse(data.get("expires_at")),
            lease_clamped_from=_parse(data.get("lease_clamped_from")),
        )


@runtime_checkable
class AuditSink(Protocol):
    """Destination for `AuditRecord`s."""

    def emit(self, record: AuditRecord) -> None: ...


class StderrJsonSink:
    """Synchronous JSON-line audit sink writing to stderr by default.

    One record per line. Flushed eagerly so records appear in process
    output without buffering surprise.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        # Default at emit-time so monkeypatch of `sys.stderr` in tests
        # is observed even if the sink was constructed earlier.
        self._stream = stream

    def emit(self, record: AuditRecord) -> None:
        stream = self._stream if self._stream is not None else sys.stderr
        json.dump(record.to_dict(), stream)
        stream.write("\n")
        stream.flush()


class CollectingSink:
    """Test sink that records every emitted `AuditRecord` in memory."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def emit(self, record: AuditRecord) -> None:
        self.records.append(record)
