# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
ucon.tools.mcp.system.startup
=============================

Server-startup configuration value.

`StartupConfig` is a frozen dataclass carrying the three knobs the
operator may set at process start to shape the dispatcher and its
process base:

- ``profile`` — default identity tier (``"standard"`` | ``"preview"``);
  drives ``Dispatcher.default_identity.tier``.
- ``system`` — forward-compat selector for a named ``UnitSystem``
  catalog; stored on ``ProcessBase.catalog`` for inspection. v0.5.0
  has no system catalog registry, so the value is opaque and is not
  resolved.
- ``tier_header`` — forward-compat name of the transport header from
  which to extract caller tier. Stored on the config; runtime
  consumers do not yet exist (transport-level identity extraction is
  scheduled post-v0.5).

Resolution layering (highest precedence first): CLI flags > env vars
> field defaults. Field defaults preserve v0.4.x behavior — no flags
and no env produce ``StartupConfig()`` equivalent to
``StartupConfig(profile="standard", system=None, tier_header=None)``.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from ucon.tools.mcp.system.value_types import TIER_CONFIGS

# Environment variable names.
ENV_PROFILE: Final[str] = "UCON_PROFILE"
ENV_SYSTEM: Final[str] = "UCON_SYSTEM"

# Sentinel used by ``with_overrides`` to distinguish "leave field alone"
# from "explicitly set to None". ``replace`` is the right primitive for
# value-type updates but doesn't support a tri-state sentinel directly.
_UNSET: Final[object] = object()


@dataclass(frozen=True)
class StartupConfig:
    """Process-startup configuration for the MCP server.

    See module docstring for field semantics and resolution layering.

    Attributes
    ----------
    profile : str
        Default identity tier. Must be a key of ``TIER_CONFIGS``.
        Defaults to ``"standard"``.
    system : str | None
        Forward-compat name of a ``UnitSystem`` catalog. Stored on
        ``ProcessBase.catalog`` so future catalog-aware code can
        resolve it; v0.5.0 ignores the value at runtime.
    tier_header : str | None
        Forward-compat transport header name. Stored but not consumed
        at runtime in v0.5.0.
    """

    profile: str = "standard"
    system: str | None = None
    tier_header: str | None = None

    def __post_init__(self) -> None:
        if self.profile not in TIER_CONFIGS:
            raise ValueError(
                f"Unknown profile {self.profile!r}; "
                f"expected one of {sorted(TIER_CONFIGS)}"
            )

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None
    ) -> "StartupConfig":
        """Build a config from environment variables.

        Reads ``UCON_PROFILE`` and ``UCON_SYSTEM``. Unset variables
        fall through to field defaults. ``UCON_PROFILE`` of empty
        string is treated as unset (matches typical shell semantics
        where ``UCON_PROFILE= ucon-mcp`` should preserve the default).
        """
        source = env if env is not None else os.environ
        profile_raw = source.get(ENV_PROFILE) or "standard"
        system_raw = source.get(ENV_SYSTEM) or None
        return cls(profile=profile_raw, system=system_raw)

    def with_overrides(
        self,
        *,
        profile: str | object = _UNSET,
        system: str | None | object = _UNSET,
        tier_header: str | None | object = _UNSET,
    ) -> "StartupConfig":
        """Return a new config with the supplied fields overridden.

        Fields left at the ``_UNSET`` sentinel are preserved. Pass
        ``None`` to explicitly clear ``system`` or ``tier_header``.
        """
        kwargs: dict[str, object] = {}
        if profile is not _UNSET:
            kwargs["profile"] = profile
        if system is not _UNSET:
            kwargs["system"] = system
        if tier_header is not _UNSET:
            kwargs["tier_header"] = tier_header
        return replace(self, **kwargs)  # type: ignore[arg-type]
