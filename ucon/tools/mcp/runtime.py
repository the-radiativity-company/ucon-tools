# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""
ucon.tools.mcp.runtime
======================

The values a server is built from and computes in.

Two things are separated here that were previously one:

``ServerConfig``
    What an embedder decides. Frozen, consumed once at construction — a
    server is configured by being *built*, never by being mutated
    afterwards.

``ServerRuntime``
    What a tool call operates in: session state, the capability
    dispatcher, and per-server caches. One per server today; one per
    tenant once a resolver keys it by identity.

Tool bodies reach their runtime through :func:`runtime_from`, which
prefers the request context the lifespan populated and falls back to a
`ContextVar` for direct (non-served) calls. The ContextVar is the only
ambient state in this layer, and it is per-context rather than
per-process — mirroring ucon's own ``_active``, so concurrent tasks get
independent views instead of racing over a module global.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterator

from ucon.tools.mcp.session import DefaultSessionState, SessionState
from ucon.tools.mcp.system import (
    CallerIdentity,
    Dispatcher,
    OperatorOverlayPolicy,
    OperatorState,
    ProcessBase,
    SessionOverlayPolicy,
    StartupConfig,
    StderrJsonSink,
    SystemClock,
    TIER_CONFIGS,
)

if TYPE_CHECKING:
    from ucon.graph import ConversionGraph


@dataclass(frozen=True)
class ToolCall:
    """One completed tool invocation, handed to a `CallHook`.

    ``duration_ms`` is wall-clock time for the tool body including
    dispatch; ``success`` is False when the body raised (the exception
    still propagates to the caller).
    """

    tool: str
    duration_ms: float
    success: bool


# Called after every tool invocation. Like `AuditSink.emit`, a hook must
# not raise: exceptions are caught and logged so instrumentation can
# never fail a tool call.
CallHook = Callable[[ToolCall], None]


@dataclass(frozen=True)
class ServerConfig:
    """Everything an embedder can decide about a server.

    Attributes
    ----------
    base_graph : ConversionGraph | None
        Base graph for session state — the composition point for
        deployments that materialize a custom graph (extra unit
        packages, a restricted system). ``None`` uses ucon's default.
    startup : StartupConfig | None
        Startup knobs (profile, system, tier header). ``None`` means
        `StartupConfig()` defaults.
    catalog : Any
        `BundleCatalog` for capability-bundle resolution. ``None``
        falls back to ``StartupConfig.system``, then to
        ``DEFAULT_CATALOG``.
    call_hook : CallHook | None
        Invoked after each tool call with a `ToolCall`. Intended for
        metrics and usage accounting.
    name : str
        Server name advertised over the protocol.
    version : str | None
        Version advertised in the ``initialize`` handshake. ``None``
        reports the installed ``ucon-tools`` version. Without this the
        SDK reports *its own* version, so a client cannot tell which
        ucon-tools it is talking to — or whether an upgrade landed.
    host, port : optional
        Bind address for HTTP transports.
    transport_security : Any
        ``TransportSecuritySettings`` for the SDK. Relevant when binding
        beyond localhost behind a trusted proxy, where the SDK's default
        DNS-rebinding protection would reject requests.
    """

    base_graph: "ConversionGraph | None" = None
    startup: StartupConfig | None = None
    catalog: Any = None
    call_hook: CallHook | None = None
    name: str = "ucon"
    version: str | None = None
    host: str | None = None
    port: int | None = None
    transport_security: Any = None


@dataclass(frozen=True)
class ServerRuntime:
    """Per-server state: what a tool call computes in.

    Replaces the module-level session, dispatcher, startup-config, and
    inline-graph-cache globals. Each server owns one; nothing is shared
    unless two servers are handed the same object deliberately.
    """

    session: SessionState
    dispatcher: Dispatcher
    config: ServerConfig
    # Memoizes compiled inline graphs (keyed by a hash of the caller's
    # definitions). Per-runtime so one server cannot serve another's
    # compilation, and so it dies with the server rather than the
    # process.
    inline_graph_cache: dict[str, "ConversionGraph"] = field(default_factory=dict)


def build_runtime(
    config: ServerConfig | None = None,
    tools: frozenset[str] | None = None,
) -> ServerRuntime:
    """Construct the runtime a server serves from.

    ``tools`` is the roster the server actually registered, passed in
    rather than discovered from a module global so ``ProcessBase.tools``
    describes *this* server.
    """
    cfg = config if config is not None else ServerConfig()
    startup = cfg.startup if cfg.startup is not None else StartupConfig()
    session = (
        DefaultSessionState(base_graph=cfg.base_graph)
        if cfg.base_graph is not None
        else DefaultSessionState()
    )
    dispatcher = Dispatcher(
        process_base=ProcessBase.from_globals(
            tools=tools,
            catalog=cfg.catalog if cfg.catalog is not None else startup.system,
        ),
        operator_state=OperatorState(),
        policies={
            "session": SessionOverlayPolicy(),
            "operator": OperatorOverlayPolicy(),
        },
        tier_configs=TIER_CONFIGS,
        clock=SystemClock(),
        sink=StderrJsonSink(),
        default_identity=CallerIdentity(tier=startup.profile, principal="local"),
    )
    return ServerRuntime(session=session, dispatcher=dispatcher, config=cfg)


# ---------------------------------------------------------------------------
# The ambient seam — for calls that arrive without a request context
# ---------------------------------------------------------------------------

_runtime: ContextVar["ServerRuntime | None"] = ContextVar(
    "ucon_mcp_runtime", default=None
)


@contextmanager
def use_runtime(runtime: ServerRuntime) -> Iterator[ServerRuntime]:
    """Bind ``runtime`` for ctx-less calls within this context.

    Lets a caller (typically a test) scope a runtime per case instead of
    resetting shared state, so leakage between cases is unrepresentable
    rather than merely discouraged.
    """
    token = _runtime.set(runtime)
    try:
        yield runtime
    finally:
        _runtime.reset(token)


def current_runtime() -> ServerRuntime:
    """The runtime bound for ctx-less calls, materializing a default.

    The default is per-context rather than per-process: a task that
    never binds one gets its own.
    """
    runtime = _runtime.get()
    if runtime is None:
        runtime = build_runtime()
        _runtime.set(runtime)
    return runtime


def set_current_runtime(runtime: ServerRuntime | None) -> None:
    """Replace the ctx-less runtime; ``None`` drops it so the next
    :func:`current_runtime` call rebuilds a default."""
    _runtime.set(runtime)


def runtime_from(ctx: Any | None) -> ServerRuntime:
    """Resolve the runtime for one call.

    The served path wins: a request carries its runtime in the context
    the lifespan populated, so ambient state can never shadow what a
    request arrived with. The ContextVar is consulted only when there is
    no usable ``ctx``.
    """
    if ctx is not None and hasattr(ctx, "request_context"):
        lifespan_ctx = getattr(ctx.request_context, "lifespan_context", None)
        if lifespan_ctx and "runtime" in lifespan_ctx:
            return lifespan_ctx["runtime"]
    return current_runtime()
