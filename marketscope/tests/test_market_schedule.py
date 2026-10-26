"""
Unit tests for MarketScope NSE & BSE Trading Schedule & Countdown Engine.
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from market_schedule import (
    IST,
    get_market_schedule_info,
    is_trading_day,
    is_market_holiday,
    get_next_trading_day,
    format_countdown_string,
)


class TestMarketScheduleEngine(unittest.TestCase):
    def test_regular_trading_hours_open(self):
        # Wednesday Oct 28, 2026 at 11:30:00 IST
        dt = datetime(2026, 10, 28, 11, 30, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertTrue(info["is_open"])
        self.assertEqual(info["state"], "OPEN")
        self.assertEqual(info["status_badge"], "LIVE OPEN")
        self.assertEqual(info["action"], "closes")
        self.assertEqual(info["target_time_ist"], "2026-10-28 15:30:00 IST")
        # 11:30 to 15:30 is 4 hours = 14,400 seconds
        self.assertEqual(info["remaining_seconds"], 14400)
        self.assertEqual(info["countdown_formatted"], "04h 00m 00s")
        self.assertEqual(info["phrase"], "Closes in 04h 00m 00s")

    def test_pre_open_session(self):
        # Wednesday Oct 28, 2026 at 09:05:00 IST
        dt = datetime(2026, 10, 28, 9, 5, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "PRE_OPEN")
        self.assertEqual(info["status_badge"], "PRE-OPEN")
        self.assertEqual(info["action"], "opens")
        self.assertEqual(info["target_time_ist"], "2026-10-28 09:15:00 IST")
        # 09:05 to 09:15 is 10 minutes = 600 seconds
        self.assertEqual(info["remaining_seconds"], 600)
        self.assertEqual(info["countdown_formatted"], "00h 10m 00s")
        self.assertEqual(info["phrase"], "Opens in 00h 10m 00s")

    def test_early_morning_pre_market(self):
        # Wednesday Oct 28, 2026 at 08:30:00 IST
        dt = datetime(2026, 10, 28, 8, 30, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "CLOSED")
        self.assertEqual(info["action"], "opens")
        self.assertEqual(info["target_time_ist"], "2026-10-28 09:15:00 IST")
        # 08:30 to 09:15 is 45 minutes = 2700 seconds
        self.assertEqual(info["remaining_seconds"], 2700)
        self.assertEqual(info["countdown_formatted"], "00h 45m 00s")

    def test_post_close_session(self):
        # Wednesday Oct 28, 2026 at 15:45:00 IST
        dt = datetime(2026, 10, 28, 15, 45, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "POST_CLOSE")
        self.assertEqual(info["action"], "opens")
        # Should target Thursday Oct 29 at 09:15:00 IST
        self.assertEqual(info["target_time_ist"], "2026-10-29 09:15:00 IST")

    def test_evening_after_hours(self):
        # Wednesday Oct 28, 2026 at 20:00:00 IST
        dt = datetime(2026, 10, 28, 20, 0, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "CLOSED")
        self.assertEqual(info["action"], "opens")
        # 20:00 to 09:15 next day is 13 hours 15 minutes = 47,700 seconds
        self.assertEqual(info["target_time_ist"], "2026-10-29 09:15:00 IST")
        self.assertEqual(info["remaining_seconds"], 47700)
        self.assertEqual(info["countdown_formatted"], "13h 15m 00s")

    def test_friday_evening_targets_monday(self):
        # Friday Oct 30, 2026 at 18:00:00 IST
        dt = datetime(2026, 10, 30, 18, 0, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["action"], "opens")
        # Should target Monday Nov 02, 2026 at 09:15:00 IST
        self.assertEqual(info["target_time_ist"], "2026-11-02 09:15:00 IST")
        self.assertTrue("d " in info["countdown_formatted"])

    def test_weekend_sunday_targets_monday(self):
        # Sunday Oct 25, 2026 at 20:00:00 IST
        dt = datetime(2026, 10, 25, 20, 0, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)

        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "WEEKEND")
        self.assertEqual(info["action"], "opens")
        self.assertEqual(info["target_time_ist"], "2026-10-26 09:15:00 IST")
        self.assertEqual(info["countdown_formatted"], "13h 15m 00s")

    def test_holiday_skips_to_next_open_day(self):
        # Republic Day: Jan 26, 2026 is Monday
        republic_day = date(2026, 1, 26)
        self.assertTrue(is_market_holiday(republic_day))
        self.assertFalse(is_trading_day(republic_day))

        next_day = get_next_trading_day(republic_day)
        self.assertEqual(next_day, date(2026, 1, 27))

        dt = datetime(2026, 1, 26, 10, 0, 0, tzinfo=IST)
        info = get_market_schedule_info(dt)
        self.assertFalse(info["is_open"])
        self.assertEqual(info["state"], "HOLIDAY")
        self.assertEqual(info["target_time_ist"], "2026-01-27 09:15:00 IST")

    def test_format_countdown_string(self):
        self.assertEqual(format_countdown_string(30), "00h 00m 30s")
        self.assertEqual(format_countdown_string(3665), "01h 01m 05s")
        self.assertEqual(format_countdown_string(90000), "1d 01h 00m 00s")


class TestScheduleServerEndpoints(unittest.TestCase):
    def test_market_schedule_endpoint(self):
        from server import MarketScopeHandler
        handler = object.__new__(MarketScopeHandler)
        sent = {}
        handler._send_json = lambda p, status=200: sent.update(p)
        handler._handle_market_schedule()
        self.assertIn("is_open", sent)
        self.assertIn("target_timestamp", sent)
        self.assertIn("countdown_formatted", sent)
        self.assertIn("phrase", sent)
        self.assertIn("exchange_hours", sent)


if __name__ == "__main__":
    unittest.main()
