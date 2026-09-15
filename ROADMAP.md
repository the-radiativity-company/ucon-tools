# Roadmap

Where `ucon-tools` is going, and what changes for people using the MCP server.

Versions ship when they are ready; the ordering below is a commitment, the
timing is not. Issue links point at the tracking work.

## Now — v0.11.0: capability and composition

Two audiences: embedders who build the MCP server into their own process,
and operators who want a server that exposes less than everything.

- **Public composition API.** A supported entry point for constructing the
  server with a custom base unit system, startup configuration, and
  per-call instrumentation. Today the only way to do this is to reach into
  `mcp._mcp_server.lifespan`, `mcp._tool_manager.call_tool`, and
  `mcp.settings` — private surfaces that break quietly. (One such breakage
  is live: patching the lifespan drops the dispatcher from the request
  context, disabling capability resolution without any error.)
- **Opt-in capability enforcement.** Bundles become enforceable: the
  advertised tool set narrows to a floor, and the rest arrives by
  activating capability bundles at startup. An unconfigured server keeps
  today's behavior exactly — every tool available — so adopting this is a
  choice, not a migration.
- **Deprecations.** The runtime bundle-activation machinery (mutable
  operator state, activation leases, runtime activate/deactivate) has no
  consumer and no path to one: lease semantics belong to whatever
  provisions the process, not to the process itself. Deprecated here,
  removed at v1.0.0.

## Next — v0.12.0: kind integrity

Adopts ucon 2.3.0, whose kind work is being designed now:

- **Kind annotations stop outliving their validity.** A conversion whose
  target unit falls outside the declared kind currently preserves the kind
  anyway, so the result asserts a label it has not earned
  ([ucon#303](https://github.com/withtwoemms/ucon/issues/303)).
- **Join policy semantics.** Whether `join_policy` inherits down the kind
  lattice is an open design question
  ([ucon#304](https://github.com/withtwoemms/ucon/issues/304)); a
  root-level `refuse` is currently unreachable because children default to
  `lca`. The answer determines what else this release needs.
- **`kind` threading on `compute`**
  ([#48](https://github.com/the-radiativity-company/ucon-tools/issues/48)),
  which also makes lattice-join behavior observable from the MCP surface
  for the first time.
- **Aspect-only validation**: whether `validate_result` should accept
  `declared_aspects` without a `declared_kind`
  ([#47](https://github.com/the-radiativity-company/ucon-tools/issues/47)).

## Then — v1.0.0: removal and freeze

The breaking release. Everything deprecated through the 0.x line comes
out, and the surface is frozen.

- **The 17 deprecated tools are removed**, leaving ten: `convert`,
  `compute`, `decompose`, `check_dimensions`, `discover`, `define`,
  `system`, `call_formula`, `validate_result`, `reset_session`. Every
  deprecated tool has carried a notice naming its replacement since
  v0.9.0.
- Legacy tool bodies are inlined into `define` and `system`. Payload
  equality between the consolidated tools and their predecessors is
  pinned by tests, so this is invisible to callers.
- Capability bundle rosters are re-cut against the final surface, and the
  deprecated runtime machinery is removed.
- The public API is frozen under semantic versioning.

### Migrating before v1.0.0

| Deprecated | Replacement |
|---|---|
| `list_units`, `list_scales`, `list_dimensions`, `list_constants`, `list_formulas`, `list_quantity_kinds`, `list_kind_formulas`, `list_extended_bases` | `discover(topic=...)` |
| `define_unit`, `define_conversion`, `define_constant`, `define_quantity_kind`, `extend_basis` | `define(kind=...)` |
| `restrict_system`, `diff_systems`, `check_compatibility` | `system(action=...)` |
| `declare_computation` | `validate_result(declared_kind=...)` |

Deprecated tools remain fully functional until v1.0.0 and return
identical payloads to their replacements.

If you consume this server through a long-lived MCP client, note that
clients cache the tool list: after upgrading, reconnect so your client
sees the current surface.
