"""
Unit Tests for Real-Time Scraper Engine & Stock Master Database
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from stock_database import StockDatabaseManager
from scraper import RealTimeScraperFeed
from server import MarketScopeHandler


class TestStockDatabase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = StockDatabaseManager(db_path=Path(self.tmp.name))

    def tearDown(self):
        try:
            import os
            os.remove(self.tmp.name)
        except Exception:
            pass

    def test_populate_and_search(self):
        sample_csv = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "TCS,Tata Consultancy Services Limited,EQ,25-AUG-2004,1,1,INE467B01029,1\n"
            "INFY,Infosys Limited,EQ,08-FEB-1995,5,1,INE009A01021,5\n"
            "RELIANCE,Reliance Industries Limited,EQ,29-NOV-1995,10,1,INE002A01018,10\n"
        )
        count = self.db.populate_from_nse_master(csv_data=sample_csv)
        self.assertEqual(count, 3)
        self.assertEqual(self.db.get_stock_count(), 3)

        res = self.db.search_stocks("TATA")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["symbol"], "TCS")
        self.assertEqual(res[0]["sector"], "Technology")

        stock = self.db.get_stock("INFY")
        self.assertIsNotNone(stock)
        self.assertEqual(stock["name"], "Infosys Limited")


class TestScraperEngine(unittest.TestCase):
    def setUp(self):
        self.feed = RealTimeScraperFeed(monitored_symbols=["TEST1", "TEST2"])

    def test_add_symbol_to_track(self):
        self.assertTrue(self.feed.add_symbol_to_track("TATAPOWER"))
        self.assertIn("TATAPOWER", self.feed.monitored_symbols)
        # Adding again should return False (already present)
        self.assertFalse(self.feed.add_symbol_to_track("TATAPOWER"))

    def test_scrape_candles_with_mock_data(self):
        mock_raw = {
            "symbol": "TEST1",
            "ticker": "TEST1.NS",
            "exchange": "NSE",
            "currency": "INR",
            "price": 105.0,
            "previous_close": 100.0,
            "day_high": 106.0,
            "day_low": 99.0,
            "timeframe": 5,
            "candles": [
                {"t": 1700000000 + i * 300, "o": 100 + i, "h": 101 + i, "l": 99 + i, "c": 100.5 + i, "v": 1000 + i * 50, "closed": True}
                for i in range(25)
            ],
        }

        with patch.object(self.feed, "scrape_stock_candles", return_value=mock_raw):
            res = self.feed._process_stock("TEST1", timeframe=5)
            self.assertIsNotNone(res)
            sym, payload, pts = res
            self.assertEqual(sym, "TEST1")
            self.assertEqual(payload["price"], 105.0)
            self.assertIn("ai_decision", payload)
            self.assertIn("action", payload["ai_decision"])
            self.assertGreater(len(pts), 0)


class TestScraperServerEndpoints(unittest.TestCase):
    def test_stocks_database_endpoint(self):
        handler = object.__new__(MarketScopeHandler)
        sent = {}
        handler._send_json = lambda p, status=200: sent.update(p)
        handler._handle_stocks_database({"q": ["TCS"], "limit": ["10"]})
        self.assertIn("stocks", sent)
        self.assertIn("total_database", sent)

    def test_stocks_track_endpoint(self):
        handler = object.__new__(MarketScopeHandler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.db = MagicMock()
        handler.db.get_latest_config.return_value = None
        handler._get_current_session = lambda: {"user_id": 1, "role": "member"}
        sent = {}
        handler._parse_json_body = MagicMock(return_value={"symbol": "SBIN"})
        handler._send_json = lambda p, status=200: sent.update(p)
        handler._handle_stocks_track()
        self.assertEqual(sent.get("status"), "success")
        self.assertEqual(sent.get("symbol"), "SBIN")


if __name__ == "__main__":
    unittest.main()
