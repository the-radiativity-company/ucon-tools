# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""
Tests for `ucon.tools.mcp.system.startup.StartupConfig`.

Invariants under test:

- `StartupConfig()` matches v0.4.x behavior: ``profile="standard"``,
  ``system=None``, ``tier_header=None``.
- `from_env` reads ``UCON_PROFILE`` and ``UCON_SYSTEM``; missing or
  empty-string values fall through to field defaults.
- `with_overrides` preserves un-passed fields via the ``_UNSET``
  sentinel; explicit ``None`` clears nullable fields.
- Invalid ``profile`` raises ``ValueError`` at construction time.
- Resolution precedence in `main` is CLI flags > env vars > defaults
  (verified via direct `with_overrides` composition; the argparse
  layer is exercised in test_server_dispatch_wiring).
"""
from __future__ import annotations

import pytest

from ucon.tools.mcp.system import (
    ENV_PROFILE,
    ENV_SYSTEM,
    StartupConfig,
    TIER_CONFIGS,
)


# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------

def test_default_config_matches_v04x_behavior():
    cfg = StartupConfig()
    assert cfg.profile == "standard"
    assert cfg.system is None
    assert cfg.tier_header is None


def test_config_is_frozen():
    cfg = StartupConfig()
    with pytest.raises(Exception):  # FrozenInstanceError
        cfg.profile = "preview"  # type: ignore[misc]


def test_config_equality_and_hash():
    a = StartupConfig(profile="preview", system="med", tier_header="X-Tier")
    b = StartupConfig(profile="preview", system="med", tier_header="X-Tier")
    assert a == b
    # Frozen dataclasses with hashable fields are hashable by default.
    assert hash(a) == hash(b)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def test_invalid_profile_raises_value_error():
    with pytest.raises(ValueError, match="Unknown profile"):
        StartupConfig(profile="root")


def test_all_known_tier_keys_accepted():
    for tier in TIER_CONFIGS:
        StartupConfig(profile=tier)  # must not raise


# -----------------------------------------------------------------------------
# from_env
# -----------------------------------------------------------------------------

def test_from_env_with_empty_mapping_yields_defaults():
    cfg = StartupConfig.from_env({})
    assert cfg == StartupConfig()


def test_from_env_reads_profile():
    cfg = StartupConfig.from_env({ENV_PROFILE: "preview"})
    assert cfg.profile == "preview"


def test_from_env_reads_system():
    cfg = StartupConfig.from_env({ENV_SYSTEM: "scientific"})
    assert cfg.system == "scientific"


def test_from_env_empty_string_falls_through_to_default():
    cfg = StartupConfig.from_env({ENV_PROFILE: "", ENV_SYSTEM: ""})
    assert cfg.profile == "standard"
    assert cfg.system is None


def test_from_env_invalid_profile_raises_at_construction():
    with pytest.raises(ValueError, match="Unknown profile"):
        StartupConfig.from_env({ENV_PROFILE: "root"})


def test_from_env_uses_os_environ_by_default(monkeypatch):
    monkeypatch.setenv(ENV_PROFILE, "preview")
    monkeypatch.setenv(ENV_SYSTEM, "med")
    cfg = StartupConfig.from_env()
    assert cfg.profile == "preview"
    assert cfg.system == "med"


def test_from_env_does_not_set_tier_header():
    # Forward-compat field has no env binding in v0.5.0.
    cfg = StartupConfig.from_env({ENV_PROFILE: "preview"})
    assert cfg.tier_header is None


# -----------------------------------------------------------------------------
# with_overrides
# -----------------------------------------------------------------------------

def test_with_overrides_preserves_untouched_fields():
    base = StartupConfig(profile="preview", system="med", tier_header="X-Tier")
    out = base.with_overrides()
    assert out == base


def test_with_overrides_replaces_profile():
    base = StartupConfig(profile="standard", system="med")
    out = base.with_overrides(profile="preview")
    assert out.profile == "preview"
    assert out.system == "med"  # untouched


def test_with_overrides_can_clear_nullable_fields():
    base = StartupConfig(profile="preview", system="med", tier_header="X-Tier")
    out = base.with_overrides(system=None, tier_header=None)
    assert out.system is None
    assert out.tier_header is None
    assert out.profile == "preview"  # untouched


def test_with_overrides_validates_new_profile():
    base = StartupConfig()
    with pytest.raises(ValueError, match="Unknown profile"):
        base.with_overrides(profile="root")


# -----------------------------------------------------------------------------
# Precedence: CLI > env > defaults
# -----------------------------------------------------------------------------

def test_precedence_env_overrides_defaults_when_no_cli():
    env_cfg = StartupConfig.from_env({ENV_PROFILE: "preview"})
    # No CLI override → env wins.
    cli_profile = None
    final = env_cfg.with_overrides(
        profile=cli_profile if cli_profile is not None else env_cfg.profile,
    )
    assert final.profile == "preview"


def test_precedence_cli_overrides_env():
    env_cfg = StartupConfig.from_env({ENV_PROFILE: "preview"})
    cli_profile = "standard"
    final = env_cfg.with_overrides(
        profile=cli_profile if cli_profile is not None else env_cfg.profile,
    )
    assert final.profile == "standard"


def test_precedence_defaults_when_neither_cli_nor_env():
    env_cfg = StartupConfig.from_env({})
    cli_profile = None
    final = env_cfg.with_overrides(
        profile=cli_profile if cli_profile is not None else env_cfg.profile,
    )
    assert final.profile == "standard"
    assert final.system is None
    assert final.tier_header is None
