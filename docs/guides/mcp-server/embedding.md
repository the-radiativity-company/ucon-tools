# Embedding the MCP Server

Running `ucon-mcp` is the common case. Embedding is for when you need the
server *inside* your own process — with a unit system you assembled, calls
you want to measure, or more than one server at a time.

`create_server` is the supported entry point. Everything it accepts was
previously reachable only by patching the SDK's private attributes, which
change without notice.

## The simplest case

```python
from ucon.tools.mcp import create_server

create_server().run(transport="stdio")
```

Defaults reproduce `ucon-mcp` exactly.

## Configuration

Everything a server can be told is a field on `ServerConfig`, consumed once
at construction. A server is configured by being *built*, never by being
mutated afterwards.

```python
from ucon.tools.mcp import create_server, ServerConfig

server = create_server(ServerConfig(
    base_graph=graph,          # a ConversionGraph you assembled
    startup=startup_config,    # profile, system, tier header
    catalog=bundle_catalog,    # capability-bundle source
    call_hook=on_call,         # per-call instrumentation
    name="ucon",               # name advertised over the protocol
    host="0.0.0.0",            # HTTP transports
    port=8000,
    transport_security=...,    # SDK TransportSecuritySettings
))
server.run(transport="streamable-http")
```

| Field | Purpose |
|---|---|
| `base_graph` | Base graph for session state — extra unit packages, a restricted system. Defaults to ucon's. |
| `startup` | `StartupConfig`: tier profile, unit-system name, tier header. |
| `catalog` | `BundleCatalog` for capability bundles. Defaults to `DEFAULT_CATALOG`. |
| `call_hook` | Called after every tool invocation. See below. |
| `name` | Server name in the protocol handshake. |
| `version` | Version reported in the `initialize` handshake. Defaults to the installed `ucon-tools` version — leave it unless you are wrapping the server in your own product and want that identity advertised instead. |
| `host`, `port` | Bind address for HTTP transports. |
| `transport_security` | Needed when binding beyond localhost behind a trusted proxy, where the SDK's default DNS-rebinding protection would reject requests. |

### A custom unit system

Pass the graph; do not try to install it afterwards.

```python
from ucon.graph import get_default_graph
from ucon.packages import load_package

graph = get_default_graph().with_package(load_package("aerospace-v1.ucon.toml"))
server = create_server(ServerConfig(base_graph=graph))
```

Every session on that server starts from your graph, and `reset_session()`
returns to it rather than to ucon's default.

## Instrumenting calls

A `call_hook` receives a `ToolCall` after every invocation — the natural
place for metrics, usage accounting, or audit events.

```python
from ucon.tools.mcp import create_server, ServerConfig

def on_call(call):
    metrics.record(call.tool, call.duration_ms, success=call.success)

server = create_server(ServerConfig(call_hook=on_call))
```

`ToolCall` carries `tool`, `duration_ms` (wall-clock, including dispatch),
and `success` (`False` when the body raised — the exception still
propagates to the caller).

A hook **must not raise**. Exceptions are caught and logged so
instrumentation can never fail a tool call, but a hook that throws on every
call will fill your logs and record nothing.

## Several servers in one process

Each `create_server` call returns an independent server. Two servers share
no session, dispatcher, configuration, or hook.

```python
internal = create_server(ServerConfig(base_graph=internal_graph))
public   = create_server(ServerConfig(startup=StartupConfig(profile="preview")))
```

A unit defined through `internal` is invisible to `public`. This is what
makes it possible to serve differently-configured callers from one process
— and to run realistic tests without resetting global state between them.

## Runtimes

A **server** is what clients connect to: tool schemas, transport, protocol.
A **runtime** is what a call computes in: session state, the capability
dispatcher, caches. Each server builds one runtime when it starts, and
tool calls resolve it from the request context.

You rarely need to touch runtimes directly. The exception is calling tools
as plain Python functions, with no MCP request in flight — tests, mostly.
Those calls resolve through a context-local runtime, and `use_runtime`
scopes one explicitly:

```python
from ucon.tools.mcp import build_runtime, use_runtime, ServerConfig

with use_runtime(build_runtime(ServerConfig())):
    result = convert(value=1, from_unit="m", to_unit="km")   # isolated
```

This is per-context, not per-process, so concurrent tasks get independent
views rather than contending over shared state.

## Migrating from the module-level `mcp`

Importing the module-level server is deprecated and will be removed in
v1.0.0:

```python
from ucon.tools.mcp.server import mcp   # DeprecationWarning
```

It reconfigured one process-wide object, so a second caller silently
rewired the first's server. Replace patching with configuration:

| Was | Now |
|---|---|
| `mcp.settings.host = ...` | `ServerConfig(host=...)` |
| `mcp.settings.port = ...` | `ServerConfig(port=...)` |
| `mcp.settings.transport_security = ...` | `ServerConfig(transport_security=...)` |
| patching `mcp._mcp_server.lifespan` to inject a graph | `ServerConfig(base_graph=...)` |
| wrapping `mcp._tool_manager.call_tool` | `ServerConfig(call_hook=...)` |
| `mcp.run(...)` | `create_server(config).run(...)` |

The lifespan patch is worth calling out. Replacing the lifespan to inject a
graph dropped the dispatcher from the request context, and every request
then fell back to a default dispatcher — silently, with no error. A server
could run for months appearing healthy while capability resolution was
disabled. Passing `base_graph` removes both the reason and the mechanism.
