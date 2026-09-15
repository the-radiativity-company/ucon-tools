# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Tests for the public composition API (`build_server`).

Contracts:

1. The lifespan always yields both ``"session"`` and ``"dispatcher"``.
   Embedders configure a custom base graph through `build_server`
   instead of replacing the lifespan — a replacement that omits
   ``"dispatcher"`` silently disables capability resolution.
2. A supplied ``base_graph`` reaches session state.
3. ``call_hook`` observes every tool call, and a raising hook can never
   fail the call it observes.
4. `build_server` does not write its `StartupConfig` into the
   process-wide global — that global also steers the fallback
   dispatcher used by direct calls, so a "preview" profile installed
   there silently strips session overlays for every caller.
"""

import asyncio
import unittest


class BuildServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ucon.tools.mcp.server import (
            build_server,
            lifespan,
            mcp,
            ServerConfig,
            ToolCall,
            _build_dispatcher,
            _get_server_config,
        )
        cls.build_server = staticmethod(build_server)
        cls.lifespan = staticmethod(lifespan)
        cls.mcp = mcp
        cls.ServerConfig = ServerConfig
        cls.ToolCall = ToolCall
        cls._build_dispatcher = staticmethod(_build_dispatcher)
        cls._get_server_config = staticmethod(_get_server_config)

    def tearDown(self):
        # Restore stock configuration so ordering cannot leak state.
        self.build_server()

    def _lifespan_context(self):
        async def run():
            async with self.lifespan(self.mcp) as ctx:
                return dict(ctx)
        return asyncio.run(run())

    def test_lifespan_yields_session_and_dispatcher(self):
        ctx = self._lifespan_context()
        self.assertIn("session", ctx)
        self.assertIn("dispatcher", ctx)
        self.assertIsNotNone(ctx["dispatcher"])

    def test_dispatcher_survives_a_custom_base_graph(self):
        """Regression: configuring a graph must not cost the dispatcher.

        The deployment wrapper used to replace the lifespan to inject a
        graph, yielding only {"session": ...}; every request then fell
        back to the fallback dispatcher with no error.
        """
        from ucon.graph import get_default_graph

        self.build_server(base_graph=get_default_graph())
        ctx = self._lifespan_context()
        self.assertIn("dispatcher", ctx)
        self.assertIsNotNone(ctx["dispatcher"])

    def test_base_graph_reaches_session_state(self):
        from ucon.tools.mcp.server import define_unit, reset_session
        from ucon.graph import get_default_graph

        graph = get_default_graph()
        self.build_server(base_graph=graph)
        ctx = self._lifespan_context()
        session = ctx["session"]
        self.assertIsNotNone(session.get_graph())
        reset_session()

    def test_stock_build_server_returns_the_module_server(self):
        self.assertIs(self.build_server(), self.mcp)

    def test_settings_passthrough(self):
        server = self.build_server(host="0.0.0.0", port=8123)
        self.assertEqual(server.settings.host, "0.0.0.0")
        self.assertEqual(server.settings.port, 8123)

    def test_config_is_recorded(self):
        from ucon.tools.mcp.system import StartupConfig

        cfg = StartupConfig(profile="preview")
        self.build_server(startup=cfg)
        self.assertIs(self._get_server_config().startup, cfg)

    def test_startup_config_does_not_leak_to_the_process_global(self):
        """Regression: `build_server` used to call `_set_startup_config`.

        That global also feeds `_get_fallback_dispatcher`, so building a
        server with `profile="preview"` made PREVIEW's
        `mutation_allowed=False` apply to *direct* tool calls too —
        session overlays were dropped and every session-defined unit
        became "Unknown unit" for the rest of the process.
        """
        from ucon.tools.mcp.server import _get_startup_config
        from ucon.tools.mcp.system import StartupConfig

        before = _get_startup_config()
        self.build_server(startup=StartupConfig(profile="preview"))
        self.assertIs(_get_startup_config(), before)


class CallHookTestCase(BuildServerTestCase):
    """The hook sees every call and can never break one."""

    def _call_tool(self, name, arguments):
        async def run():
            return await self.mcp._tool_manager.call_tool(name, arguments)
        return asyncio.run(run())

    def test_hook_observes_successful_calls(self):
        seen = []
        self.build_server(call_hook=seen.append)
        self._call_tool("convert", {"value": 1, "from_unit": "m", "to_unit": "km"})
        self.assertTrue(seen)
        call = seen[-1]
        self.assertIsInstance(call, self.ToolCall)
        self.assertEqual(call.tool, "convert")
        self.assertTrue(call.success)
        self.assertGreaterEqual(call.duration_ms, 0.0)

    def test_hook_records_failure_without_swallowing_it(self):
        seen = []
        self.build_server(call_hook=seen.append)
        with self.assertRaises(Exception):
            self._call_tool("convert", {"nonsense": True})
        self.assertTrue(seen)
        self.assertFalse(seen[-1].success)

    def test_raising_hook_does_not_fail_the_call(self):
        def boom(call):
            raise RuntimeError("instrumentation exploded")

        self.build_server(call_hook=boom)
        result = self._call_tool(
            "convert", {"value": 1, "from_unit": "m", "to_unit": "km"}
        )
        self.assertIsNotNone(result)

    def test_reconfiguring_swaps_the_hook_rather_than_nesting(self):
        first, second = [], []
        self.build_server(call_hook=first.append)
        self.build_server(call_hook=second.append)
        self._call_tool("convert", {"value": 1, "from_unit": "m", "to_unit": "km"})
        self.assertEqual(len(first), 0)
        self.assertEqual(len(second), 1)


class DispatcherCatalogTestCase(unittest.TestCase):
    """An explicit catalog overrides the `StartupConfig.system` stamp."""

    def test_explicit_catalog_is_honored(self):
        from ucon.tools.mcp.server import _build_dispatcher
        from ucon.tools.mcp.system.catalog import StaticCatalog

        catalog = StaticCatalog({})
        dispatcher = _build_dispatcher(catalog=catalog)
        self.assertIs(dispatcher.process_base.catalog, catalog)


if __name__ == "__main__":
    unittest.main()
