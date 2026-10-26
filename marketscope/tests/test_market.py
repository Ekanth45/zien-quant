"""
Unit Tests for MarketScope Technical Indicators, Calculations & Session Aggregation
"""

import unittest
from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    from tests.fixture_loader import load_test_fixtures, get_fixture_stock_candles
except ImportError:
    from fixture_loader import load_test_fixtures, get_fixture_stock_candles

from market import (
    STOCK_CATALOGUE,
    DEFAULT_CONFIG,
    calculate_ema,
    calculate_rsi,
    calculate_vwap,
    calculate_momentum,
    calculate_rvol,
    calculate_support_resistance,
    calculate_composite_score,
    calculate_order_blocks,
    aggregate_candles,
    clamp,
)


class TestMarketIndicators(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(clamp(1.5), 1.0)
        self.assertEqual(clamp(-2.0), -1.0)
        self.assertEqual(clamp(0.25), 0.25)

    def test_ema_calculation(self):
        closes = [10.0, 11.0, 12.0, 11.5, 13.0]
        ema = calculate_ema(closes, period=9)
        self.assertEqual(len(ema), len(closes))
        self.assertEqual(ema[0], 10.0)
        # alpha = 2 / 10 = 0.2
        # ema[1] = 0.2 * 11 + 0.8 * 10 = 10.2
        self.assertAlmostEqual(ema[1], 10.2)

    def test_rsi_all_gains(self):
        # 15 values -> 14 positive gains
        closes = [float(i) for i in range(15)]
        rsi = calculate_rsi(closes, period=14)
        self.assertEqual(rsi, 100.0)

    def test_rsi_all_losses(self):
        # 15 values -> 14 negative changes
        closes = [float(100 - i) for i in range(15)]
        rsi = calculate_rsi(closes, period=14)
        self.assertEqual(rsi, 0.0)

    def test_rsi_no_change(self):
        closes = [50.0] * 15
        rsi = calculate_rsi(closes, period=14)
        self.assertEqual(rsi, 50.0)

    def test_rsi_insufficient_bars(self):
        closes = [10.0, 11.0, 12.0]
        self.assertIsNone(calculate_rsi(closes, period=14))

    def test_vwap_zero_volume(self):
        candles = [{"h": 100, "l": 90, "c": 95, "v": 0}]
        self.assertIsNone(calculate_vwap(candles))

    def test_vwap_positive_volume(self):
        candles = [
            {"h": 105, "l": 95, "c": 100, "v": 100},  # tp = 100, tp*v = 10000
            {"h": 115, "l": 105, "c": 110, "v": 200},  # tp = 110, tp*v = 22000
        ]
        # Total tp*v = 32000, Total v = 300 -> 32000/300 = 106.666...
        vwap = calculate_vwap(candles)
        self.assertIsNotNone(vwap)
        self.assertAlmostEqual(vwap, 320.0 / 3.0)

    def test_momentum_5_bars(self):
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]
        # 5 bars earlier than 110.0 is 100.0
        mom = calculate_momentum(closes, period=5)
        self.assertIsNotNone(mom)
        self.assertAlmostEqual(mom, 10.0)

    def test_momentum_insufficient_bars(self):
        self.assertIsNone(calculate_momentum([100.0, 101.0], period=5))

    def test_rvol_calculation(self):
        volumes = [100.0, 100.0, 100.0, 200.0]
        # Latest bar = 200, preceding avg = 100 -> rvol = 2.0
        rvol = calculate_rvol(volumes, period=20)
        self.assertAlmostEqual(rvol, 2.0)

    def test_rvol_no_preceding(self):
        self.assertEqual(calculate_rvol([50.0]), 1.0)
        self.assertEqual(calculate_rvol([]), 1.0)

    def test_support_resistance(self):
        candles = [
            {"h": 120, "l": 90},
            {"h": 115, "l": 95},
            {"h": 130, "l": 105},
        ]
        sup, res = calculate_support_resistance(candles, period=20)
        self.assertEqual(sup, 90)
        self.assertEqual(res, 130)

    def test_composite_score_bounds(self):
        score_res = calculate_composite_score(
            fast_ema=105.0, slow_ema=100.0, momentum=2.5, close=106.0, vwap=100.0, rsi=80.0
        )
        self.assertGreaterEqual(score_res["score"], 0)
        self.assertLessEqual(score_res["score"], 100)

    def test_composite_score_bullish(self):
        score_res = calculate_composite_score(
            fast_ema=105.0, slow_ema=100.0, momentum=2.0, close=105.0, vwap=100.0, rsi=75.0, score_threshold=65
        )
        self.assertEqual(score_res["signal"], "BUY")
        self.assertGreaterEqual(score_res["score"], 65)

    def test_composite_score_bearish(self):
        score_res = calculate_composite_score(
            fast_ema=95.0, slow_ema=100.0, momentum=-2.0, close=94.0, vwap=100.0, rsi=25.0, score_threshold=65
        )
        self.assertEqual(score_res["signal"], "SELL")
        self.assertLessEqual(score_res["score"], 35)

    def test_composite_score_neutral(self):
        score_res = calculate_composite_score(
            fast_ema=100.0, slow_ema=100.0, momentum=0.0, close=100.0, vwap=100.0, rsi=50.0, score_threshold=65
        )
        self.assertEqual(score_res["signal"], "NEUTRAL")
        self.assertEqual(score_res["score"], 50)

    def test_composite_score_unavailable(self):
        score_res = calculate_composite_score(
            fast_ema=None, slow_ema=100.0, momentum=None, close=100.0, vwap=None, rsi=None
        )
        self.assertEqual(score_res["signal"], "UNAVAILABLE")
        self.assertIsNone(score_res["score"])

    def test_order_blocks_bullish_breakout(self):
        # 6 candles baseline, then 7th breaks out above highest high of prior 5
        candles = [
            {"o": 100, "h": 102, "l": 99, "c": 101, "closed": True},
            {"o": 101, "h": 103, "l": 100, "c": 102, "closed": True},
            {"o": 102, "h": 103, "l": 98, "c": 99, "closed": True},   # Opposing down candle (o=102, c=99, l=98, h=103)
            {"o": 99, "h": 101, "l": 98, "c": 100, "closed": True},
            {"o": 100, "h": 102, "l": 99, "c": 101, "closed": True},
            {"o": 101, "h": 102, "l": 100, "c": 101, "closed": True},
            {"o": 101, "h": 108, "l": 101, "c": 107, "closed": True}, # Breakout above 103!
        ]
        zones = calculate_order_blocks(candles)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]["type"], "bullish")
        self.assertEqual(zones[0]["low"], 98.0)
        self.assertEqual(zones[0]["high"], 103.0)

    def test_order_blocks_bearish_breakout(self):
        candles = [
            {"o": 100, "h": 102, "l": 99, "c": 101, "closed": True},
            {"o": 101, "h": 103, "l": 100, "c": 102, "closed": True},
            {"o": 100, "h": 104, "l": 100, "c": 103, "closed": True},  # Opposing up candle (o=100, c=103, l=100, h=104)
            {"o": 102, "h": 103, "l": 101, "c": 101, "closed": True},
            {"o": 101, "h": 102, "l": 100, "c": 101, "closed": True},
            {"o": 101, "h": 102, "l": 100, "c": 101, "closed": True},
            {"o": 100, "h": 100, "l": 90, "c": 92, "closed": True},    # Breakdown below 100!
        ]
        zones = calculate_order_blocks(candles)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]["type"], "bearish")
        self.assertEqual(zones[0]["low"], 100.0)
        self.assertEqual(zones[0]["high"], 104.0)

    def test_order_blocks_invalidation(self):
        candles = [
            {"o": 100, "h": 102, "l": 95, "c": 101, "closed": True},
            {"o": 101, "h": 103, "l": 95, "c": 102, "closed": True},
            {"o": 102, "h": 103, "l": 98, "c": 99, "closed": True},   # Opposing down candle: low=98, high=103
            {"o": 99, "h": 101, "l": 97, "c": 100, "closed": True},
            {"o": 100, "h": 102, "l": 97, "c": 101, "closed": True},
            {"o": 101, "h": 102, "l": 97, "c": 101, "closed": True},
            {"o": 101, "h": 108, "l": 101, "c": 107, "closed": True}, # Breakout -> bullish zone [98, 103]
            {"o": 105, "h": 106, "l": 97, "c": 97.5, "closed": True}, # Closes at 97.5 < 98 -> invalidates bullish zone!
        ]
        zones = calculate_order_blocks(candles)
        bullish_survivors = [z for z in zones if z["type"] == "bullish"]
        self.assertEqual(len(bullish_survivors), 0)

    def test_order_blocks_max_4(self):
        # Generate longer series with repeated breakouts
        candles = []
        price = 100.0
        for i in range(50):
            candles.append({
                "o": price,
                "h": price + 2,
                "l": price - 2,
                "c": price + 1 if i % 2 == 0 else price - 1,
                "closed": True,
            })
            price += 1.5
        zones = calculate_order_blocks(candles)
        self.assertLessEqual(len(zones), 4)

    def test_aggregate_candles_5m(self):
        c1m = [
            {"t": "2026-10-23T09:15:00+05:30", "o": 100, "h": 105, "l": 99, "c": 102, "v": 10, "closed": True},
            {"t": "2026-10-23T09:16:00+05:30", "o": 102, "h": 106, "l": 101, "c": 104, "v": 15, "closed": True},
            {"t": "2026-10-23T09:17:00+05:30", "o": 104, "h": 107, "l": 103, "c": 105, "v": 20, "closed": True},
            {"t": "2026-10-23T09:18:00+05:30", "o": 105, "h": 108, "l": 104, "c": 106, "v": 25, "closed": True},
            {"t": "2026-10-23T09:19:00+05:30", "o": 106, "h": 109, "l": 105, "c": 108, "v": 30, "closed": True},
            {"t": "2026-10-23T09:20:00+05:30", "o": 108, "h": 110, "l": 107, "c": 109, "v": 50, "closed": True},
        ]
        c5m = aggregate_candles(c1m, timeframe=5)
        self.assertEqual(len(c5m), 2)
        # First 5m bucket (09:15 - 09:19)
        self.assertEqual(c5m[0]["o"], 100)
        self.assertEqual(c5m[0]["h"], 109)
        self.assertEqual(c5m[0]["l"], 99)
        self.assertEqual(c5m[0]["c"], 108)
        self.assertEqual(c5m[0]["v"], 100)

    def test_stock_catalogue_count(self):
        self.assertEqual(len(STOCK_CATALOGUE), 24)

    def test_fixture_session_bars(self):
        fixtures = load_test_fixtures()
        stocks = fixtures.get("stocks", {})
        self.assertEqual(len(stocks), 24)
        for sym, data in stocks.items():
            bars = data["candles"]
            self.assertEqual(len(bars), 75, f"Expected 75 bars for {sym}")

    def test_snapshot_structure(self):
        fixtures = load_test_fixtures()
        snap = fixtures.get("snapshot", {})
        self.assertIn("trajectories", snap)
        self.assertIn("signal_tiles", snap)
        self.assertIn("spotlight", snap)
        self.assertIn("sectors", snap)
        self.assertIn("stocks", snap)
        self.assertEqual(len(snap["trajectories"]), 24)
        self.assertEqual(len(snap["stocks"]), 24)

    def test_trajectories_open_change(self):
        fixtures = load_test_fixtures()
        snap = fixtures.get("snapshot", {})
        for t in snap["trajectories"]:
            self.assertIn("change_pct", t)
            self.assertIn("color_group", t)
            self.assertIn(t["color_group"], ("blue", "red"))

    def test_sectors_summary(self):
        fixtures = load_test_fixtures()
        snap = fixtures.get("snapshot", {})
        sectors = snap["sectors"]
        self.assertGreater(len(sectors), 0)
        total_counted = sum(s["count"] for s in sectors)
        self.assertEqual(total_counted, 24)

    def test_reproducibility_fixture(self):
        fix1 = load_test_fixtures()
        fix2 = load_test_fixtures()
        self.assertEqual(fix1["stocks"]["RELIANCE"]["candles"][0]["o"], fix2["stocks"]["RELIANCE"]["candles"][0]["o"])
        self.assertEqual(fix1["stocks"]["TCS"]["candles"][-1]["c"], fix2["stocks"]["TCS"]["candles"][-1]["c"])

    def test_provisional_forming_candle_handling(self):
        fixtures = load_test_fixtures()
        snap = fixtures.get("snapshot", {})
        for sym, stock in snap["stocks"].items():
            self.assertIn("metrics", stock)
            self.assertIn("confirmed", stock)
            self.assertIsNotNone(stock["metrics"]["score"])

    def test_ai_decision_breakout_long(self):
        from decision_engine import evaluate_ai_decision
        metrics = {
            "score": 78,
            "signal": "BUY",
            "raw": {"rsi": 64.0, "momentum_pct": 0.8, "trend_pct": 0.35, "vwap_dist_pct": 0.4},
        }
        order_blocks = [{"type": "bullish", "low": 2420.0, "high": 2445.0}]
        decision = evaluate_ai_decision(
            symbol="RELIANCE",
            price=2450.0,
            metrics=metrics,
            vwap=2435.0,
            support=2415.0,
            resistance=2510.0,
            rvol=1.4,
            order_blocks=order_blocks,
        )
        self.assertEqual(decision["action"], "BREAKOUT LONG")
        self.assertEqual(decision["signal_type"], "BUY")
        self.assertLess(decision["stop_loss"], 2450.0)
        self.assertGreater(decision["target_1"], 2450.0)
        self.assertGreaterEqual(decision["risk_reward_ratio"], 1.5)
        # Section 2.2: R:R is in [1.5, 1.8), so conviction is capped at 60
        self.assertEqual(decision["conviction_pct"], 60)

        # When R:R >= 1.8, conviction reaches full score (>= 75)
        high_rr_decision = evaluate_ai_decision(
            symbol="RELIANCE",
            price=2450.0,
            metrics=metrics,
            vwap=2435.0,
            support=2415.0,
            resistance=2550.0,
            rvol=1.4,
            order_blocks=order_blocks,
        )
        self.assertGreaterEqual(high_rr_decision["risk_reward_ratio"], 1.8)
        self.assertGreaterEqual(high_rr_decision["conviction_pct"], 75)

    def test_ai_decision_breakdown_short(self):
        from decision_engine import evaluate_ai_decision
        metrics = {
            "score": 24,
            "signal": "SELL",
            "raw": {"rsi": 28.0, "momentum_pct": -0.9, "trend_pct": -0.4, "vwap_dist_pct": -0.6},
        }
        order_blocks = [{"type": "bearish", "low": 1470.0, "high": 1495.0}]
        decision = evaluate_ai_decision(
            symbol="INFY",
            price=1460.0,
            metrics=metrics,
            vwap=1475.0,
            support=1390.0,
            resistance=1490.0,
            rvol=1.5,
            order_blocks=order_blocks,
        )
        self.assertEqual(decision["action"], "BREAKDOWN SHORT")
        self.assertEqual(decision["signal_type"], "SELL")
        self.assertGreater(decision["stop_loss"], 1460.0)
        self.assertLess(decision["target_1"], 1460.0)
        self.assertGreaterEqual(decision["risk_reward_ratio"], 1.5)

    def test_ai_decision_range_bound(self):
        from decision_engine import evaluate_ai_decision
        metrics = {
            "score": 50,
            "signal": "NEUTRAL",
            "raw": {"rsi": 50.0, "momentum_pct": 0.0, "trend_pct": 0.0, "vwap_dist_pct": 0.0},
        }
        decision = evaluate_ai_decision(
            symbol="ITC",
            price=430.0,
            metrics=metrics,
            vwap=430.0,
            support=420.0,
            resistance=440.0,
            rvol=0.9,
            order_blocks=[],
        )
        self.assertEqual(decision["action"], "RANGE BOUND / AVOID")
        self.assertEqual(decision["signal_type"], "NEUTRAL")

    def test_snapshot_includes_ai_decision(self):
        fixtures = load_test_fixtures()
        snap = fixtures.get("snapshot", {})
        for sym, stock in snap["stocks"].items():
            self.assertIn("ai_decision", stock)
            ai = stock["ai_decision"]
            self.assertIn("action", ai)
            self.assertIn("stop_loss", ai)
            self.assertIn("target_1", ai)
            self.assertIn("risk_reward_ratio", ai)
            self.assertIn("conviction_pct", ai)


if __name__ == "__main__":
    unittest.main()
