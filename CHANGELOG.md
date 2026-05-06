# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.7] - 2026-05-06

### Added

- **`extend_basis` Phase 2 — session-scoped dimensions are real.** The
  session-aware dimension adapter introduced as non-functional groundwork
  in 0.4.6 is now wired through the tool surface. `extend_basis` graduates
  from informational-only to creating ucon `Basis` and `Dimension` objects
  that participate in the rest of the MCP toolchain for the lifetime of
  the session. Each `additional_components[*]` entry materializes a
  runtime `Dimension` that downstream tools can resolve by name or symbol.
  Components are surfaced through eight call sites that previously hard-
  coded the SI seven:
  - `define_unit` — accepts session dimensions; bypasses `UnitDef`
    materialization and constructs `Unit` directly when the dimension
    came from an extended basis
  - `list_units(dimension=...)` — filter validates against
    built-in ∪ session dimensions
  - `list_dimensions()` — now session-scoped; takes optional `Context`
    and includes dimensions created via `extend_basis`
  - `define_quantity_kind` — dimension parsing is session-aware, so KOQs
    can be declared over extended-basis dimensions
  - `list_quantity_kinds(dimension=...)` — filter is session-aware
  - `_parse_dimension_to_vector` and `_normalize_dimension_vector` —
    accept extended-basis symbols and append them after the SI canonical
    block in declaration order
  - `build_unknown_dimension_error` — suggestion pool includes session
    dimensions, so typos resolve against extended bases too
  - `_get_dimension_vector` — second pass over basis components beyond
    the SI seven so signatures render their full extended shape

- **Dimension parser papercuts closed.** `_parse_dimension_to_vector` now
  accepts forms previously rejected:
  - bare base symbols (`"M"`, `"L"`, and any extended symbol)
  - compound expressions (`"mass/time"`, `"mass*length/time^2"`)
  - dimensionless aliases (`""`, `"1"`, `"dimensionless"`)
  - `luminous_intensity` as a synonym for `luminosity`
  - `information` (mapped to `B`, the built-in SI extension)

- `tests/ucon/tools/mcp/test_extended_basis_dimensions.py` — 348-line
  fixture suite covering session-dimension registration, KOQ declaration
  over extended bases, suggestion-pool behaviour for unknown extended
  dimensions, dimension-parser acceptance of bare symbols and compound
  expressions, and signature rendering for components beyond the SI seven

### Changed

- `ExtendedBasisInfo` records carry `runtime_basis: Basis` and
  `runtime_dimensions: tuple[Dimension, ...]` fields, promoting the
  metadata record to a bridge between MCP-level descriptions and ucon-core
  basis/dimension objects. The `(Phase 1: informational only)` qualifier
  is removed from `extend_basis` response messages; the message now lists
  the new dimension names that became available.
- `_format_exponent(symbol, exp)` consolidates the unicode superscript
  branching that previously appeared inline in three call sites; symbol-
  agnostic so any extended-basis symbol renders correctly.
- ucon dependency lower bound: `ucon>=1.6.4a1` → `ucon>=1.6.5`.

### Fixed

- `_normalize_dimension_vector` previously hardcoded the SI symbol regex
  `[MLTIΘNJ]`, silently dropping extended-basis symbols when normalizing
  vector strings. The symbol set is now drawn from the session's
  registered bases with longer-symbol-first matching to disambiguate
  multi-character extended symbols from the SI seven.

## [0.4.6] - 2026-05-04

### Added

- [UnitSafe](https://huggingface.co/datasets/radiativity/UnitSafe) benchmark
  runner (`benchmarks/unitsafe/run.py`) for evaluating models on 500
  metrological reasoning problems
- UnitSafe section in README and MCP server guide with evaluation examples
- CHANGELOG gate in CI now scopes to sub-project changelogs
  (`benchmarks/unitsafe/CHANGELOG.md`) when only sub-project files change

### Added (non-functional)

- **Foundation for `extend_basis` Phase 2.** Internal session-aware dimension
  adapter layer that collapses eight scattered "what dimensions exist?" lookups
  into one extensible seam. No user-visible behavior change yet — the
  wire-through to `define_unit`, `list_units`, `list_dimensions`,
  `define_quantity_kind`, `list_quantity_kinds`,
  `_parse_dimension_to_vector`, `_normalize_dimension_vector`, and
  `build_unknown_dimension_error` is pending. Concretely:
  - `SessionState.get_session_dimensions()` protocol method + matching
    `DefaultSessionState` implementation, with a `_session_dimensions` dict
    cleared on `reset()`
  - `ExtendedBasisInfo.runtime_basis` and `runtime_dimensions` fields,
    promoting the metadata record to a bridge between MCP-level descriptions
    and ucon-core `Basis` / `Dimension` objects
  - `_all_known_dimensions(session)` helper — single source of truth for
    built-in ∪ session-created dimensions
  - `_format_exponent(symbol, exp)` helper — symbol-agnostic unicode
    superscript rendering (no longer hardcoded to SI symbols)
  - `_parse_compound_dimension(expr, known_vectors, extra_symbols)` helper —
    composes single-symbol bases through `/`, `*`, `^N` with extended-symbol
    canonical ordering
- `MANIFEST.in` to exclude benchmarks, docs, tests, scripts, and CI
  config from sdist
- `glama.json` metadata file for [Glama](https://glama.ai) MCP server registry

### Fixed

- replaces codecov badge in accordance with recent repo ownership handover
- **Typo suggestions deduplicate by target Unit.** `_suggest_units` previously
  returned multiple aliases of the same unit (e.g. `meter`, `metre`, `metres`)
  as separate fuzzy-match candidates. With ucon 1.6.4 adding plural aliases,
  the top matches for typos like `meater` were three synonyms of `meter` with
  near-identical similarity scores, defeating the 0.1 gap criterion that
  guards against ambiguous suggestions. The fuzzy-match pool is now widened
  from 3 to 5 raw candidates and collapsed by `Unit` identity (preserving
  the highest-scoring alias per cluster) before the gap and absolute-score
  thresholds run. No public API change; thresholds and scoring are unchanged.

## [0.4.5] - 2026-04-15

### Added

- **Formula output simplification.** `call_formula` now auto-simplifies
  compound output units to their named SI equivalents when the conversion
  factor is exactly 1.0 (e.g. `kg·m/s²` → `N`, `kg·m²/s²` → `J`,
  `kg·m²/s³` → `W`).

- **Cross-basis formula input tests.** Formulas now accept non-default-scale
  SI inputs (g, cm, mN) and — with ucon v1.6.3's cross-basis coercion —
  CGS-basis inputs (dyne, erg, poise) that are automatically coerced to SI
  before the formula body runs.

- **Left-to-right associativity tests** for the `convert` tool
  (`TestConvertLeftToRightAssociativity`, 5 tests):
  - `m/s*kg` parses as `(m/s)·kg`, not `m/(s·kg)`
  - `m/s*kg` ≠ `m/(s*kg)` (dimension mismatch)
  - `J/mol*K` ≠ `J/(mol*K)` — parentheses required for multi-term denominators
  - Chained division `mg/kg/day` identity
  - Parenthesized denominator `J/(mol*K)` identity

- **Constant unit integrity tests** (`TestConstantUnitIntegrity`, 3 tests):
  - `G` has unit `m³·kg⁻¹·s⁻²` (not `m³·kg⁻¹·s²`)
  - `R` has unit `J·mol⁻¹·K⁻¹` (not `J·mol⁻¹·K¹`)
  - `σ` has unit `W·m⁻²·K⁻⁴` (not `W·m⁻²·K⁴`)
  - Guards against parser associativity regressions in `ucon`

- **Decompose associativity roundtrip tests** (3 tests in tier 4):
  - `m/s*kg` → `m*kg/s` identity
  - `J/(mol*K)` identity with parenthesized denominator
  - `mg/kg/day` chained division identity

### Changed

- Minimum `ucon` dependency bumped from `>=1.6.0` to `>=1.6.3a1`
  - Required for cross-basis coercion in `@enforce_dimensions`

## [0.4.4] - 2026-04-13

### Fixed

- 12 constant-dependent formulas now call `.to_base()` on all dimensioned
  inputs before computation, eliminating scale-mismatch bugs when users
  provide non-base-SI units (km, kJ, cm³, etc.):
  - **Physics**: `gravitational_force`, `photon_energy`, `coulombs_law`,
    `projectile_range`, `schwarzschild_radius`
  - **Aerospace**: `orbital_velocity`, `escape_velocity`, `orbital_period`,
    `thrust`
  - **Chemistry**: `ideal_gas_pressure`, `gibbs_free_energy`
  - **Engineering**: `darcy_weisbach`, `kinetic_energy`
- `tsiolkovsky_delta_v` normalized from `.to(units.kilogram)` to `.to_base()`
  for consistency with the new pattern

### Notes

- Root cause: formulas extracted raw magnitudes from user-supplied units and
  combined them with physical constants defined in SI base units (G in
  m³/(kg·s²), ε₀ in F/m, etc.). Non-base inputs produced results off by
  the scale factor raised to the formula's power law.
- `Number.to_base()` has been available since ucon v1.5.0. It converts
  algebraically without consulting the ConversionGraph.
- Pure-ratio formulas (`molarity`, `dilution`, `stress`, `ohms_law_power`,
  `moles_from_mass`, SRE formulas) are unaffected — scale factors cancel.

## [0.4.3] - 2026-04-13

### Changed

- Minimum `ucon` dependency bumped from `>=1.5.0a1` to `>=1.6.0`
- Three formulas now consume `standard_gravity` (`gₙ`, exact) from
  `ucon.constants` instead of hardcoding `9.80665 m/s²`:
  - **Engineering**: `darcy_weisbach`
  - **Physics**: `projectile_range`
  - **Aerospace**: `tsiolkovsky_delta_v`
  - Numerically identical — `gₙ` is defined exact at 9.80665 m/s²
  - Aligns with the pattern used by other formulas that consume CODATA constants
    (`G`, `h`, `c`, `ε₀`)

## [0.4.2] - 2026-04-10

### Changed

- Minimum `ucon` dependency bumped from `>=1.1.2` to `>=1.5.0a1`
  - Required for 9 new physical constants added in ucon 1.5.0: `gₙ` (exact),
    `Eₕ`, `Ry`, `a₀`, `ℏ/Eₕ`, `mP`, `lP`, `tP`, `TP` (measured, CODATA 2022)
- Constant count assertions updated to reflect expanded constant catalog
  (8 exact, 3 derived, 15 measured = 26 total; was 7/3/7 = 17)

## [0.4.1] - 2026-04-05

### Fixed

- `bmi` formula now normalizes inputs to kg/m before computing, producing correct kg/m² results regardless of input units (cm, inches, lb, etc.)
- `reynolds_number` formula no longer produces 1000× error when density is provided in `kg/m³`; inputs are normalized to coherent SI units before computing the dimensionless result
- `fib4` formula accepts dimensionless AST/ALT values (removes `Dimension.frequency` constraint that rejected clinical `U/L` units)
- `error_budget_remaining` formula reimplemented using standard SRE formulation: `1 - (error_rate / allowed_error_rate)` instead of `SLO - error_rate`

### Notes

- BMI and Reynolds number fixes follow the same normalization pattern already used by BSA, CrCl, and Tsiolkovsky — extract to canonical units via `.to()` before applying the formula
- The Reynolds number root cause is a scale prefix asymmetry in `Number` algebra when mixing prefix-decomposed units (`kg` = kilo × gram) with opaque derived units (`Pa`); normalizing to floats before computing avoids the issue at the formula layer
- FIB-4's AST/ALT parameters are now unconstrained (`Number`) like platelets, matching clinical usage where enzyme activity values are passed as raw numeric U/L counts

## [0.4.0] - 2026-04-05

### Added

- 30 built-in domain formulas across 6 domains, registered at server startup and immediately available via `list_formulas` / `call_formula`:
  - **Medical** (5): `bmi`, `bsa` (Du Bois), `creatinine_clearance` (Cockcroft-Gault), `fib4`, `mean_arterial_pressure`
  - **Engineering** (5): `reynolds_number`, `ohms_law_power`, `stress`, `darcy_weisbach`, `kinetic_energy`
  - **Chemistry** (5): `ideal_gas_pressure`, `molarity`, `dilution`, `moles_from_mass`, `gibbs_free_energy`
  - **Physics** (5): `gravitational_force`, `photon_energy`, `coulombs_law`, `projectile_range`, `schwarzschild_radius`
  - **SRE** (5): `availability`, `error_budget_remaining`, `mtbf`, `mttr`, `throughput`
  - **Aerospace** (5): `orbital_velocity`, `escape_velocity`, `orbital_period`, `tsiolkovsky_delta_v`, `thrust`

### Changed

- Formula registry restructured from single module (`formulas.py`) to package (`formulas/`)
  - `formulas/_registry.py` — registry internals
  - `formulas/{medical,engineering,chemistry,physics,sre,aerospace}.py` — domain modules
  - `formulas/__init__.py` — re-exports public API and triggers domain registration on import
  - Backward compatible: `from ucon.tools.mcp.formulas import register_formula` unchanged

### Notes

- Formulas exercise 24 dimensions as inputs or outputs: mass, length, time, temperature, pressure, velocity, density, dynamic_viscosity, force, area, volume, energy, power, voltage, resistance, frequency, charge, amount_of_substance, concentration, molar_mass, entropy, angle, information, and dimensionless
- Empirical formulas (BSA, Cockcroft-Gault, FIB-4, Tsiolkovsky) normalize inputs to canonical units before applying coefficients
- Physics and aerospace formulas consume CODATA 2022 constants (`G`, `h`, `c`, `ε₀`) from `ucon.constants`; uncertainty propagates to results automatically

## [0.3.2] - 2026-04-03

### Fixed

- `decompose` structured mode: constraint solver replaces greedy placement heuristic
  - Correctly handles concentration problems where quantities must be placed in both numerator and denominator (e.g., 250 mL in numerator, 400 mg in denominator)
  - Brute-force 2^N solver over sign assignments with Occam tiebreaker (fewest denominators) and literal unit name matching against initial unit factors
  - Falls back to greedy scorer for N > 10 quantities
- `decompose` structured mode: auto-bridging of residual unit mismatches
  - After quantity placement, detects and inserts scale conversion factors (e.g., mcg → mg, min → h) so the factor chain produces the correct numeric result
  - Handles both cancelling pairs (mcg⁺¹ · mg⁻¹) and surviving unit mismatches (min⁻¹ vs h⁻¹)
- `decompose` structured mode: bare-count diagnostic for dimensionless quantities
  - When `ea` (dimensionless count) is provided but cannot fill a dimensional gap, returns an actionable error suggesting rate forms (e.g., `ea/d`, `ea/h`, `ea/min`)
  - Quantities expressed as rates (e.g., `3 ea/d`) are handled correctly by the constraint solver
- `decompose` query mode: cross-basis conversions (CGS ↔ SI) no longer rejected as dimension mismatches (e.g., `Pa*s → poise`, `dyne → N`, `m²/s → stokes`)
- Fuzzy unit suggestions crashed on unknown units due to stale `_UNIT_REGISTRY` import path (`ucon.units` → `ucon.resolver`)
- Inline `slug` test replaced with `smoot` to avoid collision with built-in `slug` unit added in ucon 1.1.x

### Changed

- Minimum `ucon` dependency bumped from `>=1.0.0` to `>=1.1.2`
- Decompose eval suite expanded: `1 GB to MB`, `1e-9 m to nm`, `1 TiB to GiB` now tested directly (requires ucon 1.1.2 resolver fixes and binary prefix support)
- Structured mode eval tests added to live server eval script

## [0.3.1] - 2026-04-01

### Fixed

- `DimConstraint` reference in `mcp.schema` (#9)

## [0.3.0] - 2026-03-31

### Added

- `decompose` MCP tool for deterministic unit conversion path construction
  - Query mode: simple "X to Y" conversions (e.g., "500 mL to L")
  - Structured mode: multi-step dimensional analysis with known quantities
  - Returns factor chains consumable by `compute`
- `expected_unit` parameter on `compute` tool for result validation
- Dimension mismatch diagnostics with corrective hints
- Eval script and Makefile target (`eval-decompose-live`)

## [0.2.1] - 2026-03-25

### Added

- Affine conversion support in `define_conversion` tool
  - `offset` parameter for affine conversions (e.g., temperature scales)
  - Conversion formula: `dst = factor * src + offset`
  - `offset` field added to `ConversionDefinitionResult`
  - Inline `custom_edges` also support `offset`
  - Backward compatible: `offset` defaults to `0.0` (linear behavior)

### Changed

- Minimum `ucon` dependency bumped from `>=0.9.3` to `>=0.10.1` (requires `EdgeDef.offset`)
- Test imports migrated from `ucon.mcp` to `ucon.tools.mcp` (aligns with ucon 0.10.x namespace)

## [0.2.0] - 2026-03-11

### Added

- Kind-of-Quantity (KOQ) tools for semantic disambiguation of dimensionally degenerate quantities:
  - `define_quantity_kind` — Register custom quantity kinds per session
  - `declare_computation` — Declare expected quantity kind before computing
  - `validate_result` — Validate result dimensions and detect semantic conflicts in reasoning
- Semantic conflict detection: `validate_result` analyzes reasoning text for keyword conflicts (e.g., mentioning "ΔH" when declared kind is "gibbs_energy")
- `KOQError` response type with structured error information and hints
- New response types: `QuantityKindDefinitionResult`, `ComputationDeclaration`, `ValidationResult`

### Fixed

- Dimension vector comparison now uses canonical SI order (M, L, T, I, Θ, N, J), fixing false mismatches from ordering differences

### Notes

- KOQ tools address the "unit-correct, KOQ-wrong" error class where LLMs compute correct numeric values with correct units but misidentify the physical quantity
- See [Kind-of-Quantity](https://docs.ucon.dev/architecture/kind-of-quantity) for conceptual background

## [0.1.0] - 2026-02-28

### Fixed

- Documentation: Updated install instructions to `ucon-tools[mcp]`
- Documentation: Updated import paths from `ucon.mcp` to `ucon.tools.mcp`

### Added

- MCP server for AI agent integration (extracted from ucon v0.9.3)
  - `convert` tool with dimensional validation
  - `compute` tool for multi-step factor-label calculations
  - `check_dimensions` compatibility tool
  - `list_units`, `list_scales`, `list_dimensions` discovery tools
  - `list_constants`, `define_constant` for physical constants
  - `define_unit`, `define_conversion`, `reset_session` for runtime extension
  - `list_formulas`, `call_formula` for dimensionally-typed calculations
- Error suggestions with fuzzy matching and confidence tiers
- Session state persistence across tool calls
- `ucon-mcp` CLI entry point
- Documentation for MCP server setup and usage

### Notes

- Requires `ucon>=0.9.4` (namespace package support)
- MCP functionality requires Python 3.10+ (FastMCP dependency)
- Install via `pip install ucon-tools[mcp]`

<!-- Links -->
[0.4.4]: https://github.com/withtwoemms/ucon-tools/compare/0.4.3...0.4.4
[0.4.3]: https://github.com/withtwoemms/ucon-tools/compare/0.4.2...0.4.3
[0.4.2]: https://github.com/withtwoemms/ucon-tools/compare/0.4.1...0.4.2
[0.4.1]: https://github.com/withtwoemms/ucon-tools/compare/0.4.0...0.4.1
[0.4.0]: https://github.com/withtwoemms/ucon-tools/compare/0.3.2...0.4.0
[0.3.2]: https://github.com/withtwoemms/ucon-tools/compare/0.3.1...0.3.2
[0.3.1]: https://github.com/withtwoemms/ucon-tools/compare/0.3.0...0.3.1
[0.3.0]: https://github.com/withtwoemms/ucon-tools/compare/0.2.1...0.3.0
[0.2.1]: https://github.com/withtwoemms/ucon-tools/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/withtwoemms/ucon-tools/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/withtwoemms/ucon-tools/releases/tag/0.1.0
