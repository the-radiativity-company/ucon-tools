# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Tests for server construction (`create_server`) and the runtime model.

Contracts:

1. Each `create_server` call yields an independent server. Two servers in
   one process share no session, dispatcher, config, or call hook.
2. A lifespan always yields ``runtime``, ``session``, and ``dispatcher``,
   all derived from one object so they cannot disagree. Embedders supply
   a base graph through `ServerConfig` rather than replacing the
   lifespan — a replacement that omitted ``dispatcher`` silently
   disabled capability resolution.
3. `call_hook` observes that server's calls only, and a raising hook can
   never fail the call it observes.
4. Registering via `add_tool` produces tool definitions identical to the
   decorator form, so construction does not alter the wire surface.
"""

import asyncio
import json
import unittest


class ServerConstructionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.runtime import (
            ServerConfig,
            ServerRuntime,
            ToolCall,
            build_runtime,
            current_runtime,
            use_runtime,
        )
        from ucon.tools.mcp.server import (
            _lifespan_for,
            _registered_tool_names,
            create_server,
            default_server,
        )
        from ucon.tools.mcp.system import StartupConfig

        cls.ServerConfig = ServerConfig
        cls.ServerRuntime = ServerRuntime
        cls.ToolCall = ToolCall
        cls.build_runtime = staticmethod(build_runtime)
        cls.current_runtime = staticmethod(current_runtime)
        cls.use_runtime = staticmethod(use_runtime)
        cls._lifespan_for = staticmethod(_lifespan_for)
        cls._registered_tool_names = staticmethod(_registered_tool_names)
        cls.create_server = staticmethod(create_server)
        cls.default_server = staticmethod(default_server)
        cls.StartupConfig = StartupConfig

    def _enter_lifespan(self, config=None):
        cfg = config if config is not None else self.ServerConfig()
        server = self.create_server(cfg)

        async def run():
            async with self._lifespan_for(cfg)(server) as ctx:
                return dict(ctx)
        return asyncio.run(run())


class TestIndependence(ServerConstructionTestCase):
    """Two servers in one process share nothing."""

    def test_each_call_returns_a_distinct_server(self):
        self.assertIsNot(self.create_server(), self.create_server())

    def test_servers_have_independent_runtimes(self):
        a = self._enter_lifespan()
        b = self._enter_lifespan()
        self.assertIsNot(a["runtime"], b["runtime"])
        self.assertIsNot(a["session"], b["session"])
        self.assertIsNot(a["dispatcher"], b["dispatcher"])

    def test_differing_profiles_do_not_leak_between_servers(self):
        """Regression: configuration used to travel by process global.

        Building a server with `profile="preview"` installed PREVIEW's
        `mutation_allowed=False` process-wide, so session overlays were
        dropped for *every* caller and session-defined units became
        "Unknown unit" for the rest of the process.
        """
        preview = self._enter_lifespan(
            self.ServerConfig(startup=self.StartupConfig(profile="preview"))
        )
        standard = self._enter_lifespan()
        self.assertEqual(preview["dispatcher"].default_identity.tier, "preview")
        self.assertEqual(standard["dispatcher"].default_identity.tier, "standard")

    def test_session_definitions_do_not_cross_servers(self):
        a = self._enter_lifespan()
        b = self._enter_lifespan()
        from ucon.core import Unit
        from ucon import Dimension

        a["session"].get_graph().register_unit(
            Unit(name="privateunit", dimension=Dimension.length)
        )
        self.assertIsNotNone(a["session"].get_graph().resolve_unit("privateunit"))
        self.assertIsNone(b["session"].get_graph().resolve_unit("privateunit"))

    def test_inline_graph_cache_is_per_runtime(self):
        a = self._enter_lifespan()
        b = self._enter_lifespan()
        self.assertIsNot(a["runtime"].inline_graph_cache,
                         b["runtime"].inline_graph_cache)

    def test_default_server_is_cached(self):
        self.assertIs(self.default_server(), self.default_server())


class TestLifespan(ServerConstructionTestCase):
    """The lifespan always yields a complete, self-consistent context."""

    def test_yields_runtime_session_and_dispatcher(self):
        ctx = self._enter_lifespan()
        for key in ("runtime", "session", "dispatcher"):
            self.assertIn(key, ctx)

    def test_keys_are_derived_from_one_runtime(self):
        ctx = self._enter_lifespan()
        self.assertIs(ctx["session"], ctx["runtime"].session)
        self.assertIs(ctx["dispatcher"], ctx["runtime"].dispatcher)

    def test_dispatcher_survives_a_custom_base_graph(self):
        """Regression: configuring a graph must not cost the dispatcher.

        Embedders used to replace the lifespan to inject a graph,
        yielding only {"session": ...}; every request then fell back to
        a default dispatcher with no error.
        """
        from ucon.graph import get_default_graph

        ctx = self._enter_lifespan(
            self.ServerConfig(base_graph=get_default_graph())
        )
        self.assertIn("dispatcher", ctx)
        self.assertIsNotNone(ctx["dispatcher"])

    def test_base_graph_reaches_session_state(self):
        from ucon.graph import get_default_graph

        ctx = self._enter_lifespan(
            self.ServerConfig(base_graph=get_default_graph())
        )
        self.assertIsNotNone(ctx["session"].get_graph())

    def test_config_is_carried_on_the_runtime(self):
        cfg = self.ServerConfig(startup=self.StartupConfig(profile="preview"))
        ctx = self._enter_lifespan(cfg)
        self.assertIs(ctx["runtime"].config, cfg)

    def test_settings_passthrough(self):
        server = self.create_server(
            self.ServerConfig(host="0.0.0.0", port=8123)
        )
        self.assertEqual(server.settings.host, "0.0.0.0")
        self.assertEqual(server.settings.port, 8123)


class TestCallHook(ServerConstructionTestCase):
    """A hook sees its own server's calls and can never break one."""

    def _call(self, server, name, arguments):
        async def run():
            return await server._tool_manager.call_tool(name, arguments)
        return asyncio.run(run())

    def _convert_args(self):
        return {"value": 1, "from_unit": "m", "to_unit": "km"}

    def test_hook_observes_successful_calls(self):
        seen = []
        server = self.create_server(self.ServerConfig(call_hook=seen.append))
        self._call(server, "convert", self._convert_args())
        self.assertTrue(seen)
        call = seen[-1]
        self.assertIsInstance(call, self.ToolCall)
        self.assertEqual(call.tool, "convert")
        self.assertTrue(call.success)
        self.assertGreaterEqual(call.duration_ms, 0.0)

    def test_hook_records_failure_without_swallowing_it(self):
        seen = []
        server = self.create_server(self.ServerConfig(call_hook=seen.append))
        with self.assertRaises(Exception):
            self._call(server, "convert", {"nonsense": True})
        self.assertTrue(seen)
        self.assertFalse(seen[-1].success)

    def test_raising_hook_does_not_fail_the_call(self):
        def boom(call):
            raise RuntimeError("instrumentation exploded")

        server = self.create_server(self.ServerConfig(call_hook=boom))
        self.assertIsNotNone(
            self._call(server, "convert", self._convert_args())
        )

    def test_hooks_are_isolated_between_servers(self):
        first, second = [], []
        server_a = self.create_server(self.ServerConfig(call_hook=first.append))
        server_b = self.create_server(self.ServerConfig(call_hook=second.append))
        self._call(server_a, "convert", self._convert_args())
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)

    def test_server_without_a_hook_is_uninstrumented(self):
        seen = []
        self.create_server(self.ServerConfig(call_hook=seen.append))
        plain = self.create_server()
        self._call(plain, "convert", self._convert_args())
        self.assertEqual(seen, [])


class TestRegistrationParity(ServerConstructionTestCase):
    """`add_tool` registration must not alter the wire surface.

    Guards an SDK upgrade silently changing how definitions are derived:
    the decorator form is what shipped through v0.10.x, so a fresh
    server's definitions must match it exactly.
    """

    def test_definitions_match_the_decorator_form(self):
        from mcp.server.fastmcp import FastMCP
        from ucon.tools.mcp.server import _TOOLS

        decorated = FastMCP("ucon")
        for fn in _TOOLS:
            decorated.tool()(fn)
        constructed = self.create_server()

        async def dump(server):
            tools = await server.list_tools()
            return {t.name: t.model_dump(mode="json") for t in tools}

        a = asyncio.run(dump(decorated))
        b = asyncio.run(dump(constructed))
        self.assertEqual(set(a), set(b))
        self.assertEqual(
            json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
        )

    def test_every_registered_tool_is_present(self):
        server = self.create_server()
        names = asyncio.run(server.list_tools())
        self.assertEqual(
            {t.name for t in names}, set(self._registered_tool_names())
        )

    def test_context_injection_is_preserved(self):
        """The registered callables are `_dispatched_tool` wrappers; if
        the signature were lost, the SDK would stop injecting `ctx` and
        dispatch would break without the schema changing."""
        server = self.create_server()
        self.assertEqual(server._tool_manager._tools["convert"].context_kwarg, "ctx")


class TestRuntimeSeam(ServerConstructionTestCase):
    """The ContextVar seam serves ctx-less callers only."""

    def test_use_runtime_scopes_a_runtime(self):
        scoped = self.build_runtime(self.ServerConfig())
        outer = self.current_runtime()
        with self.use_runtime(scoped):
            self.assertIs(self.current_runtime(), scoped)
        self.assertIs(self.current_runtime(), outer)

    def test_current_runtime_materializes_a_default(self):
        self.assertIsInstance(self.current_runtime(), self.ServerRuntime)

    def test_served_context_wins_over_the_ambient_runtime(self):
        """A request carries its runtime; ambient state must not shadow it."""
        from ucon.tools.mcp.server import _get_session

        served = self.build_runtime(self.ServerConfig())
        ambient = self.build_runtime(self.ServerConfig())

        class _Ctx:
            class request_context:  # noqa: N801 - mirrors the SDK's shape
                lifespan_context = {"runtime": served}

        with self.use_runtime(ambient):
            self.assertIs(_get_session(_Ctx()), served.session)


if __name__ == "__main__":
    unittest.main()
