"""HTTP entry points remain usable when no market data service is running."""

from contextlib import ExitStack
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import server as server_module
from security import RateLimiter


class QuietWorkspaceHandler(server_module.MarketScopeHandler):
    def log_message(self, format, *args):
        pass


class TestWorkspaceRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        patches = ExitStack()
        cls.addClassCleanup(patches.close)
        # Static pages must work without creating a database, scraper, or archive.
        for name in ("DatabaseManager", "get_live_scraper_feed", "get_candle_archive", "get_stock_database"):
            patches.enter_context(patch.object(server_module, name, side_effect=AssertionError(f"Unexpected {name}")))
        patches.enter_context(patch.object(server_module, "rate_limiter", RateLimiter(limit=1000, window_sec=60)))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietWorkspaceHandler)
        cls.httpd.db_manager = object()
        cls.httpd.signal_journal = object()
        cls.thread = Thread(target=cls.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

        def close_server():
            cls.httpd.shutdown()
            cls.httpd.server_close()
            cls.thread.join(timeout=2)

        cls.addClassCleanup(close_server)

    def get(self, path):
        connection = HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_home_and_index_open_new_workspace(self):
        expected = (server_module.STATIC_DIR / "workspace.html").read_bytes()
        for path in ("/", "/index.html", "/?session=previous"):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, expected)
                self.assertIn("text/html", headers["Content-Type"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_flow_and_legacy_terminal_routes_are_preserved(self):
        routes = {
            "/flow": "flow.html",
            "/flow.html": "flow.html",
            "/matrix": "terminal_flow_matrix.html",
            "/terminal": "terminal_flow_matrix.html",
            "/console": "orderblock_flow_console.html",
            "/orderblock": "orderblock_flow_console.html",
            "/bloomberg": "bloomberg_terminal.html",
            "/terminal-bloomberg": "bloomberg_terminal.html",
            "/mobile": "mobile_terminal.html",
            "/static/index.html": "index.html",
        }
        for route, filename in routes.items():
            with self.subTest(route=route):
                status, _, body = self.get(route)
                self.assertEqual(status, 200)
                self.assertEqual(body, (server_module.STATIC_DIR / filename).read_bytes())

    def test_workspace_assets_serve_without_market_data(self):
        for filename in ("workspace.html", "workspace.css", "workspace.js", "workspace-api.js", "favicon.svg"):
            with self.subTest(filename=filename):
                status, headers, body = self.get(f"/static/{filename}")
                self.assertEqual(status, 200)
                self.assertEqual(body, (server_module.STATIC_DIR / filename).read_bytes())
                self.assertEqual(int(headers["Content-Length"]), len(body))
                self.assertTrue(body)


class TestAnalysisSymbolValidation(unittest.TestCase):
    def make_handler(self):
        handler = object.__new__(server_module.MarketScopeHandler)
        handler.db = MagicMock()
        handler.db.get_latest_config.return_value = {"monitored_symbols": []}
        handler._get_current_session = MagicMock(return_value=None)
        handler._send_json = MagicMock()
        return handler

    def test_unknown_symbol_returns_404_before_feed_or_archive_access(self):
        for method in ("GET", "POST"):
            with self.subTest(method=method), ExitStack() as patches:
                handler = self.make_handler()
                stock_database = MagicMock()
                stock_database.get_stock.return_value = None
                patches.enter_context(patch.object(server_module, "get_stock_database", return_value=stock_database))
                feed = patches.enter_context(patch.object(server_module, "get_live_scraper_feed"))
                archive = patches.enter_context(patch.object(server_module, "get_candle_archive"))
                if method == "GET":
                    handler._handle_ai_analyze({"symbol": ["NONEXISTENT"], "poll": ["1"]})
                else:
                    handler._parse_json_body = MagicMock(return_value={"symbol": "NONEXISTENT", "poll": True})
                    handler._handle_ai_analyze()
                self.assertEqual(handler._send_json.call_args.kwargs["status"], 404)
                stock_database.get_stock.assert_called_once_with("NONEXISTENT")
                feed.assert_not_called()
                archive.assert_not_called()

    def test_catalogue_symbol_keeps_feed_unavailable_response(self):
        handler = self.make_handler()
        with patch.object(server_module, "get_session_state", return_value={"session_state": "LIVE"}), \
                patch.object(server_module, "get_candle_archive"), \
                patch.object(server_module, "get_live_scraper_feed", side_effect=RuntimeError("offline")), \
                patch.object(server_module, "get_stock_database") as catalogue:
            handler._handle_ai_analyze({"symbol": ["RELIANCE"], "poll": ["1"]})
        catalogue.assert_not_called()
        self.assertEqual(handler._send_json.call_args.kwargs["status"], 503)
        self.assertEqual(handler._send_json.call_args.args[0]["error"], "feed_unavailable")

    def test_owner_tracked_symbol_does_not_require_catalogue_lookup(self):
        handler = self.make_handler()
        handler.db.get_latest_config.return_value = {"monitored_symbols": ["TRACKED"]}
        stock = {"symbol": "TRACKED", "status": "ok"}
        with patch.object(server_module, "get_session_state", return_value={"session_state": "LIVE"}), \
                patch.object(server_module, "get_candle_archive"), \
                patch.object(server_module, "get_live_scraper_feed") as feed, \
                patch.object(server_module, "get_laya_engine") as engine, \
                patch.object(server_module, "get_stock_database") as catalogue:
            feed.return_value.get_snapshot.return_value = {"stocks": {"TRACKED": stock}}
            engine.return_value.analyze_stock.return_value = {"symbol": "TRACKED", "action": "WAIT"}
            handler._handle_ai_analyze({"symbol": ["TRACKED"], "poll": ["1"]})
        catalogue.assert_not_called()
        self.assertEqual(handler._send_json.call_args.args[0]["symbol"], "TRACKED")
        engine.return_value.analyze_stock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
