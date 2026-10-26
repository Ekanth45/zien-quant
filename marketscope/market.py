"""
MarketScope - NSE Market Analysis Engine
Deterministic technical indicator calculations, candle aggregation,
and signal scoring.
"""

from __future__ import annotations
import math
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from decision_engine import evaluate_ai_decision
except ImportError:
    from marketscope.decision_engine import evaluate_ai_decision

# IST Timezone (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# 24 Supported NSE Equity Symbols & Metadata
STOCK_CATALOGUE: Dict[str, Dict[str, Any]] = {
    "RELIANCE": {"name": "Reliance Industries", "sector": "Energy", "base_price": 2450.0},
    "HDFCBANK": {"name": "HDFC Bank", "sector": "Banking", "base_price": 1520.0},
    "INFY": {"name": "Infosys", "sector": "Technology", "base_price": 1480.0},
    "TCS": {"name": "Tata Consultancy Services", "sector": "Technology", "base_price": 3920.0},
    "ICICIBANK": {"name": "ICICI Bank", "sector": "Banking", "base_price": 1150.0},
    "BHARTIARTL": {"name": "Bharti Airtel", "sector": "Telecom", "base_price": 1320.0},
    "ITC": {"name": "ITC Limited", "sector": "Consumer", "base_price": 430.0},
    "LT": {"name": "Larsen & Toubro", "sector": "Industrials", "base_price": 3580.0},
    "SBIN": {"name": "State Bank of India", "sector": "Banking", "base_price": 780.0},
    "AXISBANK": {"name": "Axis Bank", "sector": "Banking", "base_price": 1180.0},
    "SUNPHARMA": {"name": "Sun Pharmaceutical", "sector": "Healthcare", "base_price": 1680.0},
    "TITAN": {"name": "Titan Company", "sector": "Consumer", "base_price": 3420.0},
    "MARUTI": {"name": "Maruti Suzuki", "sector": "Auto", "base_price": 11950.0},
    "BAJFINANCE": {"name": "Bajaj Finance", "sector": "Finance", "base_price": 6850.0},
    "HINDUNILVR": {"name": "Hindustan Unilever", "sector": "Consumer", "base_price": 2380.0},
    "TATASTEEL": {"name": "Tata Steel", "sector": "Metals", "base_price": 150.0},
    "JSWSTEEL": {"name": "JSW Steel", "sector": "Metals", "base_price": 920.0},
    "ONGC": {"name": "Oil & Natural Gas Corp.", "sector": "Energy", "base_price": 260.0},
    "NTPC": {"name": "NTPC Limited", "sector": "Energy", "base_price": 380.0},
    "M&M": {"name": "Mahindra & Mahindra", "sector": "Auto", "base_price": 2750.0},
    "WIPRO": {"name": "Wipro Limited", "sector": "Technology", "base_price": 510.0},
    "DRREDDY": {"name": "Dr. Reddy's Laboratories", "sector": "Healthcare", "base_price": 6600.0},
    "POWERGRID": {"name": "Power Grid Corporation", "sector": "Energy", "base_price": 310.0},
    "ULTRACEMCO": {"name": "UltraTech Cement", "sector": "Industrials", "base_price": 10800.0},
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "brand_name": "MarketScope",
    "tagline": "NSE Flow Terminal & Directional Intelligence",
    "fast_ema_period": 9,
    "slow_ema_period": 21,
    "rsi_period": 14,
    "score_threshold": 65,
    "default_timeframe": 5,
    "refresh_interval_ms": 2000,
    "formula_approved": True,
    "calendar_year": 2026,
    "holidays": ["2026-01-26", "2026-03-25", "2026-04-14", "2026-05-01", "2026-08-15", "2026-10-02", "2026-11-08"],
    "monitored_symbols": list(STOCK_CATALOGUE.keys()),

    # Composite Score Weights (sum = 100)
    "weight_trend": 35.0,
    "weight_momentum": 30.0,
    "weight_vwap": 20.0,
    "weight_rsi": 15.0,

    # Composite Normalizers
    "norm_trend": 0.4,
    "norm_momentum": 1.2,
    "norm_vwap": 0.8,
    "norm_rsi": 30.0,

    # Decision Engine Score Cutoffs
    "score_breakout_long": 70,
    "score_pullback_long": 65,
    "score_breakdown_short": 30,
    "score_pullback_short": 35,

    # Decision Engine RSI Bands
    "rsi_pullback_long_min": 42.0,
    "rsi_pullback_long_max": 68.0,
    "rsi_pullback_short_min": 32.0,
    "rsi_pullback_short_max": 58.0,
    "rsi_overbought": 76.0,

    # Minimum Risk Percentages
    "min_risk_pct_breakout": 0.006,
    "min_risk_pct_pullback": 0.005,

    # Risk-Reward Multipliers and Hurdles
    "min_rr_hurdle": 1.5,
    "conviction_rr_hurdle": 1.8,
    "rr_target1_mult": 1.5,
    "rr_target2_mult": 2.6,

    # Grade Thresholds
    "grade_aplus_rr": 2.2,
    "grade_aplus_rvol": 1.5,
    "grade_aplus_momentum": 1.2,
    "grade_a_rr": 1.8,

    # Flow Terminal & Funnel Defaults
    "flow_movers_count": 8,
    "flow_rvol_min": 1.2,
    "flow_score_threshold": 65,
    "flow_rr_min": 1.5,
}


def clamp(val: float, low: float = -1.0, high: float = 1.0) -> float:
    """Clamp value between [low, high]."""
    return max(low, min(high, val))


def calculate_ema(closes: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Exponential Moving Average.
    alpha = 2 / (period + 1)
    EMA[0] = closes[0]
    EMA[t] = alpha * closes[t] + (1 - alpha) * EMA[t-1]
    """
    if not closes or period <= 0:
        return []
    alpha = 2.0 / (period + 1.0)
    ema_list: List[Optional[float]] = []
    ema = closes[0]
    ema_list.append(ema)
    for price in closes[1:]:
        ema = alpha * price + (1.0 - alpha) * ema
        ema_list.append(ema)
    return ema_list


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Welles Wilder smoothed RSI.
    Seed with the simple average of the first `period` changes, then smooth:
      avg_gain = (prev_avg_gain * (period - 1) + gain) / period
      avg_loss = (prev_avg_loss * (period - 1) + loss) / period
    Returns None when fewer than period + 1 closes are available.
    """
    if len(closes) < period + 1 or period <= 0:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    seed_changes = changes[:period]

    avg_gain = sum(max(c, 0.0) for c in seed_changes) / float(period)
    avg_loss = sum(max(-c, 0.0) for c in seed_changes) / float(period)

    for c in changes[period:]:
        gain = max(c, 0.0)
        loss = max(-c, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / float(period)
        avg_loss = (avg_loss * (period - 1) + loss) / float(period)

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_vwap(candles: List[Dict[str, Any]]) -> Optional[float]:
    """
    Calculate candle-based VWAP:
    typical_price = (high + low + close) / 3
    VWAP = sum(typical_price * volume) / sum(volume)
    """
    if not candles:
        return None
    tot_vol = 0.0
    tot_tp_vol = 0.0
    for c in candles:
        v = float(c.get("v", 0))
        if v <= 0:
            continue
        tp = (float(c["h"]) + float(c["l"]) + float(c["c"])) / 3.0
        tot_vol += v
        tot_tp_vol += tp * v

    if tot_vol <= 0:
        return None
    return tot_tp_vol / tot_vol


def calculate_momentum(closes: List[float], period: int = 5) -> Optional[float]:
    """
    Calculate five-bar momentum percentage:
    100 * (latest_close / close_five_bars_earlier - 1)
    """
    if len(closes) <= period:
        return None
    past = closes[-1 - period]
    if past <= 0:
        return None
    return 100.0 * (closes[-1] / past - 1.0)


def calculate_rvol(volumes: List[float], period: int = 20) -> float:
    """
    Relative volume: latest bar volume / mean of up to 20 preceding bar volumes.
    Excludes the latest bar from the denominator.
    """
    if not volumes:
        return 1.0
    latest = volumes[-1]
    preceding = volumes[:-1][-period:]
    if not preceding:
        return 1.0
    avg = sum(preceding) / len(preceding)
    if avg <= 0:
        return 1.0
    return latest / avg


def calculate_support_resistance(candles: List[Dict[str, Any]], period: int = 20) -> Tuple[float, float]:
    """
    Rolling support (lowest low) and resistance (highest high) of up to `period` latest bars.
    """
    if not candles:
        return 0.0, 0.0
    subset = candles[-period:]
    support = min(float(c["l"]) for c in subset)
    resistance = max(float(c["h"]) for c in subset)
    return support, resistance


def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    """
    Calculate Welles Wilder Average True Range (ATR).
    TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
    Seed with the simple average of the first `period` TRs, then smooth:
      atr = (prev_atr * (period - 1) + tr) / period
    Returns None when fewer than 2 candles are available.
    """
    if not candles or len(candles) < 2 or period <= 0:
        return None

    tr_list: List[float] = []
    for i in range(1, len(candles)):
        h = float(candles[i].get("h", candles[i].get("high", 0.0)))
        l = float(candles[i].get("l", candles[i].get("low", 0.0)))
        prev_c = float(candles[i - 1].get("c", candles[i - 1].get("close", 0.0)))
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)

    if not tr_list:
        return None
    if len(tr_list) < period:
        return round(sum(tr_list) / len(tr_list), 4)

    atr = sum(tr_list[:period]) / float(period)
    for tr in tr_list[period:]:
        atr = (atr * (period - 1) + tr) / float(period)
    return round(atr, 4)


def calculate_composite_score(
    fast_ema: Optional[float],
    slow_ema: Optional[float],
    momentum: Optional[float],
    close: float,
    vwap: Optional[float],
    rsi: Optional[float],
    score_threshold: int = 65,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate the MarketScope Composite Directional Score (0 to 100):
    - EMA trend: 100 * (fast_EMA / slow_EMA - 1) -> w_trend * clamp(trend / norm_trend)
    - Momentum: 5-bar % change -> w_mom * clamp(momentum / norm_mom)
    - VWAP dist: 100 * (close / VWAP - 1) -> w_vwap * clamp(dist / norm_vwap)
    - RSI direction: RSI - 50 -> w_rsi * clamp((RSI - 50) / norm_rsi)
    score = round(50 + weighted_sum / 2)
    """
    if fast_ema is None or slow_ema is None or slow_ema <= 0 or momentum is None or rsi is None:
        return {
            "score": None,
            "signal": "UNAVAILABLE",
            "components": {},
            "raw": {},
        }

    cfg = config or DEFAULT_CONFIG
    w_trend = float(cfg.get("weight_trend", 35.0))
    w_mom = float(cfg.get("weight_momentum", 30.0))
    w_vwap = float(cfg.get("weight_vwap", 20.0))
    w_rsi = float(cfg.get("weight_rsi", 15.0))

    norm_trend = float(cfg.get("norm_trend", 0.4))
    norm_mom = float(cfg.get("norm_momentum", 1.2))
    norm_vwap = float(cfg.get("norm_vwap", 0.8))
    norm_rsi = float(cfg.get("norm_rsi", 30.0))

    thresh = int(cfg.get("score_threshold", score_threshold))

    trend_raw = 100.0 * (fast_ema / slow_ema - 1.0)
    trend_contrib = w_trend * clamp(trend_raw / norm_trend)

    momentum_raw = momentum
    momentum_contrib = w_mom * clamp(momentum_raw / norm_mom)

    if vwap is not None and vwap > 0:
        vwap_dist_raw = 100.0 * (close / vwap - 1.0)
        vwap_contrib = w_vwap * clamp(vwap_dist_raw / norm_vwap)
    else:
        vwap_dist_raw = 0.0
        vwap_contrib = 0.0

    rsi_raw = rsi
    rsi_contrib = w_rsi * clamp((rsi - 50.0) / norm_rsi)

    weighted_sum = trend_contrib + momentum_contrib + vwap_contrib + rsi_contrib
    score = round(50.0 + weighted_sum / 2.0)
    score = max(0, min(100, int(score)))

    if score >= thresh:
        signal = "BUY"
    elif score <= (100 - thresh):
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    return {
        "score": score,
        "signal": signal,
        "components": {
            "trend": round(trend_contrib, 2),
            "momentum": round(momentum_contrib, 2),
            "vwap": round(vwap_contrib, 2),
            "rsi": round(rsi_contrib, 2),
        },
        "raw": {
            "trend_pct": round(trend_raw, 3),
            "momentum_pct": round(momentum_raw, 3),
            "vwap_dist_pct": round(vwap_dist_raw, 3),
            "rsi": round(rsi_raw, 2),
        },
    }


def calculate_order_blocks(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Order-block zone heuristic:
    For each candidate candle starting at index 6 (must be closed):
    - Bullish breakout: closes strictly above highest high of previous 5 candles.
      Origin: search backwards in those 5 candles for the most recent down candle.
      Zone: low to high range of that opposing candle.
    - Bearish breakout: closes strictly below lowest low of previous 5 candles.
      Origin: search backwards in those 5 candles for the most recent up candle.
      Zone: low to high range of that opposing candle.
    - Invalidation:
      Bullish zone invalidated if any subsequent closed candle closes below its low.
      Bearish zone invalidated if any subsequent closed candle closes above its high.
    Returns up to the last 4 surviving active zones.
    """
    if len(candles) < 7:
        return []

    active_zones: List[Dict[str, Any]] = []

    for i in range(6, len(candles)):
        curr = candles[i]
        if not curr.get("closed", True):
            continue

        c_close = float(curr["c"])
        prev_5 = candles[i - 5:i]
        high_prev_5 = max(float(c["h"]) for c in prev_5)
        low_prev_5 = min(float(c["l"]) for c in prev_5)

        # Check for Bullish Breakout
        if c_close > high_prev_5:
            # Find most recent opposing (down) candle in prev 5: close < open
            found = False
            for j in range(i - 1, i - 6, -1):
                cand = candles[j]
                if float(cand["c"]) < float(cand["o"]):
                    active_zones.append({
                        "type": "bullish",
                        "low": round(float(cand["l"]), 2),
                        "high": round(float(cand["h"]), 2),
                        "index": j,
                        "time": cand.get("t"),
                        "breakout_index": i,
                    })
                    found = True
                    break
            if not found:
                # Fallback to candle with close <= open
                for j in range(i - 1, i - 6, -1):
                    cand = candles[j]
                    if float(cand["c"]) <= float(cand["o"]):
                        active_zones.append({
                            "type": "bullish",
                            "low": round(float(cand["l"]), 2),
                            "high": round(float(cand["h"]), 2),
                            "index": j,
                            "time": cand.get("t"),
                            "breakout_index": i,
                        })
                        break

        # Check for Bearish Breakout
        elif c_close < low_prev_5:
            # Find most recent opposing (up) candle in prev 5: close > open
            found = False
            for j in range(i - 1, i - 6, -1):
                cand = candles[j]
                if float(cand["c"]) > float(cand["o"]):
                    active_zones.append({
                        "type": "bearish",
                        "low": round(float(cand["l"]), 2),
                        "high": round(float(cand["h"]), 2),
                        "index": j,
                        "time": cand.get("t"),
                        "breakout_index": i,
                    })
                    found = True
                    break
            if not found:
                # Fallback to candle with close >= open
                for j in range(i - 1, i - 6, -1):
                    cand = candles[j]
                    if float(cand["c"]) >= float(cand["o"]):
                        active_zones.append({
                            "type": "bearish",
                            "low": round(float(cand["l"]), 2),
                            "high": round(float(cand["h"]), 2),
                            "index": j,
                            "time": cand.get("t"),
                            "breakout_index": i,
                        })
                        break

        # Check invalidation of existing zones by current candle close
        surviving: List[Dict[str, Any]] = []
        for zone in active_zones:
            if zone["breakout_index"] >= i:
                surviving.append(zone)
                continue
            if zone["type"] == "bullish" and c_close < zone["low"]:
                continue  # Invalidated
            if zone["type"] == "bearish" and c_close > zone["high"]:
                continue  # Invalidated
            surviving.append(zone)
        active_zones = surviving

    # Return up to last 4 surviving zones
    return active_zones[-4:]


def aggregate_candles(candles_1m: List[Dict[str, Any]], timeframe: int = 5) -> List[Dict[str, Any]]:
    """
    Aggregate 1-minute candles into timeframe buckets (1m, 5m, 15m, 60m),
    anchored at 09:15 IST each session day.
    """
    if timeframe <= 1 or not candles_1m:
        return candles_1m

    buckets: List[Dict[str, Any]] = []
    current_bucket: Optional[Dict[str, Any]] = None
    current_bucket_idx: Optional[int] = None

    for c in candles_1m:
        # Parse timestamp or minute index
        dt_str = c.get("t", "")
        try:
            dt = datetime.fromisoformat(dt_str)
            # Minute of session from 09:15
            minutes_from_open = (dt.hour - 9) * 60 + (dt.minute - 15)
        except Exception:
            minutes_from_open = len(buckets) * timeframe

        bucket_idx = max(0, minutes_from_open // timeframe)

        if current_bucket_idx != bucket_idx:
            if current_bucket is not None:
                current_bucket["closed"] = True
                buckets.append(current_bucket)
            current_bucket = {
                "t": c["t"],
                "o": float(c["o"]),
                "h": float(c["h"]),
                "l": float(c["l"]),
                "c": float(c["c"]),
                "v": int(c.get("v", 0)),
                "closed": bool(c.get("closed", True)),
            }
            current_bucket_idx = bucket_idx
        else:
            current_bucket["h"] = max(current_bucket["h"], float(c["h"]))
            current_bucket["l"] = min(current_bucket["l"], float(c["l"]))
            current_bucket["c"] = float(c["c"])
            current_bucket["v"] += int(c.get("v", 0))
            if not c.get("closed", True):
                current_bucket["closed"] = False

    if current_bucket is not None:
        buckets.append(current_bucket)

    return buckets


