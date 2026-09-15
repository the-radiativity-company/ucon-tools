# ucon-tools Roadmap

> *Major milestones from the first MCP surface through v1.0.0. `CHANGELOG.md` is the source of truth for incremental updates.*

---

## Vision

`ucon-tools` is the interface layer that puts dimensional analysis in reach of
language models. It does not reimplement unit semantics — it delegates to
`ucon` — and it is judged on whether an agent can reach the right answer
without knowing the library.

**Target users:**

- Agent authors who want unit correctness as a tool call, not a prompt
- Operators embedding the MCP server into a hosted or multi-tenant product
- Domain teams whose units and quantity kinds are not in anyone's standard catalog

---

## How This Document Relates to CHANGELOG

This roadmap tracks **major milestones** on the path to v1.0.0. For
incremental updates — every patch and minor release, including bug fixes,
error-message refinements, and small API additions — see `CHANGELOG.md`. The
CHANGELOG is the source of truth; this roadmap exists only to surface the
structural waypoints that connect releases into a coherent trajectory.

---

## Milestone Timeline

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.4.x | First MCP surface: conversion, computation, decomposition, session-scoped custom units | Complete |
| **v0.5.0** | **Capability substrate.** Ships the ucon v1.8 `UnitSystem` through the tool surface and introduces the capability framework — `CapabilityBundle`, `BundleCatalog`, `ProcessBase`, `OverlayPolicy`, tier-driven `Dispatcher` — as frozen value types with a single mutable surface (`OperatorState`) | Complete |
| v0.5.x | Scalability metadata (`Unit.scalable`), alias resolution, non-scalable error surface | Complete |
| v0.6.0 | ucon v2.0 compatibility train (2.0.0a1 → a3) | Complete |
| v0.7.0 | Closes the ucon v2.0 full-adoption gaps | Complete |
| **v0.8.0** | **KOQ tool surface.** Surfaces ucon v2.1.x kind-of-quantity capabilities through tool signatures and closes the B5 gap — `validate_result` enforces *kind*, not merely dimension | Complete |
| **v0.9.0** | **Tool-surface consolidation (phase 1 of 2).** Discovery collapses behind `discover(topic=…)`, session definition behind `define(kind=…)`, system operations behind `system(action=…)`; seventeen superseded tools deprecated in place against a ten-tool target | Complete |
| v0.9.1 | `system(action="diff")` baselines on the pre-mutation system rather than comparing the session against itself | Complete |
| **v0.10.0** | **Aspect stratum.** Adopts ucon 2.2.0: `define(kind="aspect")`, `discover(topic="aspects")`, aspect threading through `convert`/`compute`, aspect-aware `validate_result`, D3 namespace qualification | Complete |
| v0.10.1 | Error-hint correction; assay regression gaps pinned (`applies_to` paths, consolidated/legacy payload parity) | Complete |
| **v0.11.0** | **Capability and composition.** A public composition API for embedders, opt-in capability enforcement, and deprecation of the runtime bundle-activation machinery | In progress |
| v0.12.0 | Server identity: `serverInfo` reports the ucon-tools version instead of the MCP SDK's | In progress |
| **v0.13.0** | **Kind reachability.** `kind` threading on `compute`, making lattice-join behavior observable from the MCP surface for the first time; aspect-only validation contract | Planned |
| v0.14.0 | **Kind integrity.** Adopts ucon 2.3.0 once `default_kind` lands — kind annotations stop outliving their validity | Planned |
| **v1.0.0** | **Removal and freeze.** The seventeen deprecated tools come out, legacy bodies inline into `define`/`system`, bundle rosters re-cut, runtime machinery removed, public API frozen under semantic versioning | Planned |

---

## v0.9.0–v0.10.x — The Consolidation Line

**Theme:** Shrink the surface an agent must reason about, without removing
anything a caller depends on.

**Motivation:**
A tool surface is a prompt. Twenty-four tools, eight of which differ only in
what they enumerate and five of which differ only in what they define, spend
an agent's attention on tool selection rather than on the problem. The
consolidation replaces families that share a verb with one tool keyed by a
discriminator: `discover(topic=…)`, `define(kind=…)`, `system(action=…)`.

The criterion was deliberately narrow — a family qualifies only when its
members share a verb and differ by an enumerable value. `convert`, `compute`,
and `decompose` look like a family but differ in input *shape*, not in a
discriminator; merging them would produce a union of unrelated schemas, which
is the failure mode consolidation is meant to avoid.

**Why two phases:**
Deprecate in v0.9.0, remove in v1.0.0. Every superseded tool remains
functional and returns payloads identical to its replacement — a property
pinned by tests, not asserted in prose — so callers migrate on their own
schedule rather than on the release's. The phase split is what makes the
eventual removal a non-event.

**Status:** Complete. Seventeen tools deprecated; ten remain at v1.0.0.

---

## v0.11.0 — Capability and Composition

**Theme:** Make the capability framework usable by the deployments that need
it, and make embedding the server a supported act rather than an exercise in
private-attribute archaeology.

**Motivation:**
The capability framework shipped in v0.5.0 as a complete, well-factored
substrate — frozen value types, one mutable surface, a single dispatch seam —
and has never enforced anything in production. Two structural reasons:
`ProcessBase.tools` is populated by registry introspection, so the effective
tool set is the union of everything with everything and the gate cannot
exclude; and no shipped configuration activates a bundle.

The second gap is sharper. Embedding this server in another process requires
patching `mcp._mcp_server.lifespan`, `mcp._tool_manager.call_tool`, and
`mcp.settings` — private surfaces with no stability contract. One such patch
is actively harmful: replacing the lifespan to inject a custom graph drops the
dispatcher from the request context, so every request falls back to a default
dispatcher and capability resolution is silently disabled. A deployment can
run for months believing it has a capability system.

**Scope:**

- **Public composition API.** `create_server(config)` builds a fully
  configured, independent server from a frozen `ServerConfig`. Each
  server owns its lifespan, runtime, tool roster, and call hook, so two
  in one process share nothing. Config reaches the lifespan by closure
  rather than module state, which makes the failure mode above
  unreachable by construction — there is no longer a mechanism an
  embedder would replace.
- **No module-level server state.** Eight mutable globals collapse to
  one `ContextVar` seam for calls that arrive without a request
  context. Beyond tidiness this is a prerequisite: hosting more than one
  tenant in a process is impossible while one session is the process's
  session.
- **Opt-in enforcement.** Bundles become enforceable without breaking
  existing deployments: an unconfigured server keeps today's behavior.
- **Deprecations.** The runtime bundle-activation machinery is deprecated
  here and removed at v1.0.0 — see *Open questions* below.

**Why before the kind work:**
The original plan sequenced kind integrity first. It was swapped because the
ucon-side design ruling that gates it is still open, and because both the new
public API and the new deprecations benefit from more soak time before the
v1.0.0 freeze. Ordering by what is unblocked beats ordering by what is
urgent.

**Open questions:**
Deprecating runtime activation contradicts the v0.5.0 design intent, where
timed capability control — leases with a sane default, operator
activate/deactivate, staged rollout and rollback — is the stated purpose of
the tier plan. The counter-argument is that the only deployment consuming
this server provisions one container per customer, which places lease
semantics at the provisioning layer rather than inside the process. Settling
this decides whether `ActiveBundle`, `expires_at`, lease clamping, and two of
the four audit-event literals survive to v1.0.0.

**Status:** In progress.

---

## v0.13.0 — Kind Reachability

**Theme:** You cannot verify what you cannot exercise.

**Motivation:**
No tool on this surface combines two kinds. `compute` threads `aspects`
but not `kind`, so lattice-join behavior — including whether a
`join_policy` of `refuse` ever fires — is unobservable from the wire.

That gap has already cost real diagnostic effort. A live-server assay
reported that root-level `refuse` was unreachable, inferring it from the
`join_policy` *fields* declared on child kinds because no tool could
actually perform a join. The inference was wrong: `KindLattice.lca`
returns the policy declared at the ancestor a join lands on, and the
refusal fires correctly ([ucon#304](https://github.com/withtwoemms/ucon/issues/304),
closed as not-a-bug). Confirming that required dropping to the library.
A tool that performs a join would have answered it from the wire in one
call.

**Scope:** Thread `kind` through `compute` — initial quantity and
per-factor, symmetric with `aspects` — folding kinds through the lattice
join alongside the numeric pipeline, with `JoinRefused` and
`DisjointKinds` surfacing as typed errors the way `aspect_refused`
already does
([#48](https://github.com/the-radiativity-company/ucon-tools/issues/48)).
Settle whether `validate_result` should accept declared aspects without
a declared kind
([#47](https://github.com/the-radiativity-company/ucon-tools/issues/47)).

**Not gated on `ucon`.** The lattice join works today; this release only
makes it reachable.

**Status:** Planned.

---

## v0.14.0 — Kind Integrity

**Theme:** A kind annotation should be a claim the library can stand behind.

**Motivation:**
A conversion whose target unit falls outside the declared kind preserves
the kind anyway — `1 Gy` converted to sieverts stays tagged
`absorbed_dose`, so the result asserts a label it has not earned
([ucon#303](https://github.com/withtwoemms/ucon/issues/303)). This is
worse than the known gap where an undecorated conversion is simply
silent: a missing annotation omits provenance, while a preserved one
manufactures it, and a downstream consumer has no signal that the label
is unearned.

The fix is not available to this repository. `ucon` has no unit→kind
association at all, so nothing can decide that `Sv` lies outside
`absorbed_dose`; the missing datum is `default_kind`, a declared
unit-level field arriving in ucon 2.3.0
([ucon#305](https://github.com/withtwoemms/ucon/issues/305)). One design
question is still open there — whether arrival at a unit with a
conflicting `default_kind` re-kinds the result or refuses it. Currency
wants re-kinding; dose does not, since nothing performed the weighting
that would make the target kind true.

**Scope:** Adopt ucon 2.3.0 and surface its refusals through the tool
surface as typed errors.

**Status:** Planned. Gated on ucon 2.3.0.

---

## v1.0.0 — Removal and Freeze

**Theme:** The breaks, and only the breaks.

**Scope:**

- The seventeen deprecated tools are removed, leaving ten: `convert`,
  `compute`, `decompose`, `check_dimensions`, `discover`, `define`, `system`,
  `call_formula`, `validate_result`, `reset_session`.
- Legacy tool bodies inline into `define` and `system`. Payload equality with
  their predecessors is pinned by tests, so the inlining is invisible to
  callers.
- Capability bundle rosters are re-cut against the final surface; deprecated
  runtime machinery is removed.
- The public API is frozen under semantic versioning.

**Prerequisite outside this repository:**
MCP clients cache tool lists. Until the deployment platform can tell a
connected client that the surface changed — or documents that a reconnect is
required — removal leaves clients advertising tools that no longer exist.
Schema freshness is enabling infrastructure for this release, not polish.
v0.12.0 supplies the first half — an endpoint now reports which
ucon-tools it runs, so staleness is at least detectable. Making a client
act on that remains outside this repository.

### Migrating before v1.0.0

| Deprecated | Replacement |
|---|---|
| `list_units`, `list_scales`, `list_dimensions`, `list_constants`, `list_formulas`, `list_quantity_kinds`, `list_kind_formulas`, `list_extended_bases` | `discover(topic=…)` |
| `define_unit`, `define_conversion`, `define_constant`, `define_quantity_kind`, `extend_basis` | `define(kind=…)` |
| `restrict_system`, `diff_systems`, `check_compatibility` | `system(action=…)` |
| `declare_computation` | `validate_result(declared_kind=…)` |

Deprecated tools remain fully functional until v1.0.0 and return payloads
identical to their replacements.

**Status:** Planned.

---

## Guiding Principle

> "A tool surface is a prompt.
> What it omits, the agent cannot use;
> what it asserts, the agent will believe."
