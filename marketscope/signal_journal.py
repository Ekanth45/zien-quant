"""MarketScope Signal Journal and Outcome Tracker.

Manages recording of trading setups (non-AVOID, grade >= B), 30-minute deduplication,
candle-by-candle outcome tracking with conservative same-candle SL resolution,
and statistical aggregation for backtesting and performance analytics.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("marketscope.signal_journal")


class SignalJournal:
    """Manages the lifecycle of generated trade setups and tracks realized outcomes."""

    def __init__(self, db_manager: Any):
        self.db = db_manager

    def log_snapshot_signals(
        self,
        snapshot: Dict[str, Any],
        timeframe: int = 5,
        config_version: int = 1,
    ) -> List[int]:
        """Record valid trade setups from a live snapshot into the signals table.

        Rules:
        - Only log during LIVE session mode (never historical or closed sessions).
        - Only log stocks with status == 'ok'.
        - Exclude 'AVOID' actions.
        - Grade must be at least 'B' (i.e., 'A+', 'A', 'B').
        - 30-minute deduplication window for (symbol, timeframe, action).
        """
        data_mode = snapshot.get("data_mode", "")
        session_state = snapshot.get("session_state", "")
        if data_mode != "LIVE" or (session_state and session_state != "LIVE"):
            return []

        stocks = snapshot.get("stocks", {})
        inserted_ids: List[int] = []
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            for symbol, data in stocks.items():
                if data.get("status") != "ok":
                    continue

                decision = data.get("ai_decision") or data.get("decision", {})
                action = decision.get("action", "")
                grade = decision.get("grade", "C")
                score_raw = data.get("score")
                if score_raw is None:
                    score_raw = data.get("metrics", {}).get("score", 50)
                score = int(score_raw)

                is_gated = bool(
                    decision.get("gated") == 1
                    or ("AVOID - POOR R:R" in action and (score >= 65 or score <= 35))
                )

                if is_gated:
                    gated_flag = 1
                    gate_reason = decision.get("gate_reason", "R:R < 1.5")
                    shadow_sl = decision.get("shadow_stop_loss")
                    shadow_t1 = decision.get("shadow_target_1")
                    shadow_t2 = decision.get("shadow_target_2")
                    shadow_rr = decision.get("shadow_rr") or decision.get("risk_reward_ratio")
                    sl = shadow_sl
                    t1 = shadow_t1
                    t2 = shadow_t2
                    rr = shadow_rr
                else:
                    gated_flag = 0
                    gate_reason = None
                    shadow_sl = None
                    shadow_t1 = None
                    shadow_t2 = None
                    shadow_rr = None
                    if not action or "AVOID" in action or grade not in ("A+", "A", "B"):
                        continue

                price = data.get("price")
                if not price or price <= 0:
                    continue

                # Deduplication check: no new row for (symbol, timeframe, action) within 30 min (1800s)
                cur.execute(
                    """
                    SELECT created_at FROM signals
                    WHERE symbol = ? AND timeframe = ? AND action = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (symbol, timeframe, action),
                )
                last_row = cur.fetchone()
                if last_row:
                    try:
                        last_time = datetime.fromisoformat(last_row["created_at"])
                        if (now - last_time).total_seconds() < 1800.0:
                            # Within 30 min dedupe window, skip
                            continue
                    except Exception:
                        pass

                entry_zone = decision.get("entry_zone") or [price, price]
                entry_low = float(entry_zone[0]) if len(entry_zone) > 0 and entry_zone[0] is not None else price
                entry_high = float(entry_zone[1]) if len(entry_zone) > 1 and entry_zone[1] is not None else price
                if not is_gated:
                    sl = decision.get("stop_loss")
                    t1 = decision.get("target_1")
                    t2 = decision.get("target_2")
                    rr = decision.get("risk_reward_ratio")
                conviction = int(decision.get("conviction_pct", 50))
                metrics = data.get("metrics", {})
                rvol = metrics.get("rvol")
                rsi = metrics.get("rsi")
                vwap = metrics.get("vwap")

                cur.execute(
                    """
                    INSERT INTO signals (
                        created_at, symbol, timeframe, action, grade, score, conviction,
                        price, entry_low, entry_high, stop_loss, target_1, target_2,
                        rr, rvol, rsi, vwap, config_version, outcome, mfe_pct, mae_pct,
                        gated, gate_reason, shadow_stop_loss, shadow_target_1, shadow_target_2, shadow_rr
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 0.0, 0.0, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now_iso, symbol, timeframe, action, grade, score, conviction,
                        price, entry_low, entry_high, sl, t1, t2,
                        rr, rvol, rsi, vwap, config_version,
                        gated_flag, gate_reason, shadow_sl, shadow_t1, shadow_t2, shadow_rr,
                    ),
                )
                inserted_ids.append(cur.lastrowid)

            conn.commit()
        finally:
            conn.close()

        return inserted_ids

    def update_outcomes(
        self,
        candles_by_symbol: Dict[str, List[Dict[str, Any]]],
        is_session_closed: bool = False,
    ) -> int:
        """Evaluate open signals against subsequent candles.

        Rules:
        - SL hit -> outcome = 'SL'
        - T1 hit -> outcome = 'T1', T2 hit -> outcome = 'T2'
        - If both SL and T1 hit in the same candle: outcome = 'SL' (conservative)
        - Session close: expire any remaining OPEN signals -> 'EXPIRED'
        - Track MFE (Maximum Favorable Excursion) and MAE (Maximum Adverse Excursion)
        """
        conn = self.db.get_connection()
        updated_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM signals WHERE outcome = 'OPEN'")
            open_signals = [dict(r) for r in cur.fetchall()]

            for sig in open_signals:
                symbol = sig["symbol"]
                candles = candles_by_symbol.get(symbol, [])
                if not candles and not is_session_closed:
                    continue

                sig_time_str = sig["created_at"]
                try:
                    sig_time = datetime.fromisoformat(sig_time_str)
                except Exception:
                    sig_time = datetime.min.replace(tzinfo=timezone.utc)

                action = sig["action"].upper()
                entry = sig["price"]
                sl = sig["stop_loss"] or sig.get("shadow_stop_loss")
                t1 = sig["target_1"] or sig.get("shadow_target_1")
                t2 = sig["target_2"] or sig.get("shadow_target_2")
                mfe = sig.get("mfe_pct", 0.0) or 0.0
                mae = sig.get("mae_pct", 0.0) or 0.0

                is_long = "LONG" in action or "BUY" in action or (bool(sig.get("gated")) and t1 and t1 > entry)
                is_short = "SHORT" in action or "SELL" in action or (bool(sig.get("gated")) and t1 and t1 < entry)

                resolved_outcome: Optional[str] = None
                outcome_price: Optional[float] = None

                for c in candles:
                    c_time_val = c.get("time")
                    # Check if candle is after signal creation
                    if isinstance(c_time_val, str):
                        try:
                            c_dt = datetime.fromisoformat(c_time_val)
                            if c_dt < sig_time:
                                continue
                        except Exception:
                            pass

                    high = float(c["high"])
                    low = float(c["low"])
                    close = float(c["close"])

                    if is_long:
                        favorable = (high - entry) / entry * 100.0 if entry > 0 else 0.0
                        adverse = (entry - low) / entry * 100.0 if entry > 0 else 0.0
                        mfe = max(mfe, favorable)
                        mae = max(mae, adverse)

                        sl_hit = sl is not None and low <= sl
                        t1_hit = t1 is not None and high >= t1
                        t2_hit = t2 is not None and high >= t2

                        if sl_hit and t1_hit:
                            # Conservative rule: same candle SL + T1 -> SL
                            resolved_outcome = "SL"
                            outcome_price = sl
                            break
                        elif sl_hit:
                            resolved_outcome = "SL"
                            outcome_price = sl
                            break
                        elif t2_hit:
                            resolved_outcome = "T2"
                            outcome_price = t2
                            break
                        elif t1_hit:
                            resolved_outcome = "T1"
                            outcome_price = t1
                            break

                    elif is_short:
                        favorable = (entry - low) / entry * 100.0 if entry > 0 else 0.0
                        adverse = (high - entry) / entry * 100.0 if entry > 0 else 0.0
                        mfe = max(mfe, favorable)
                        mae = max(mae, adverse)

                        sl_hit = sl is not None and high >= sl
                        t1_hit = t1 is not None and low <= t1
                        t2_hit = t2 is not None and low <= t2

                        if sl_hit and t1_hit:
                            # Conservative rule: same candle SL + T1 -> SL
                            resolved_outcome = "SL"
                            outcome_price = sl
                            break
                        elif sl_hit:
                            resolved_outcome = "SL"
                            outcome_price = sl
                            break
                        elif t2_hit:
                            resolved_outcome = "T2"
                            outcome_price = t2
                            break
                        elif t1_hit:
                            resolved_outcome = "T1"
                            outcome_price = t1
                            break

                if not resolved_outcome and is_session_closed:
                    resolved_outcome = "EXPIRED"
                    outcome_price = candles[-1]["close"] if candles else entry

                if resolved_outcome:
                    cur.execute(
                        """
                        UPDATE signals
                        SET outcome = ?, outcome_at = ?, outcome_price = ?, mfe_pct = ?, mae_pct = ?
                        WHERE id = ?
                        """,
                        (resolved_outcome, now_iso, outcome_price, round(mfe, 2), round(mae, 2), sig["id"]),
                    )
                    updated_count += 1
                elif mfe != sig.get("mfe_pct") or mae != sig.get("mae_pct"):
                    cur.execute(
                        "UPDATE signals SET mfe_pct = ?, mae_pct = ? WHERE id = ?",
                        (round(mfe, 2), round(mae, 2), sig["id"]),
                    )

            conn.commit()
        finally:
            conn.close()

        return updated_count

    def _calc_subset_stats(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Helper to aggregate performance metrics across a subset of signals."""
        total = len(signals)
        if total == 0:
            return {
                "total_signals": 0,
                "win_rate_pct": 0.0,
                "average_rr": 0.0,
                "outcomes": {"OPEN": 0, "T1": 0, "T2": 0, "SL": 0, "EXPIRED": 0},
                "by_grade": {
                    "A+": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                    "A": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                    "B": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                },
                "by_action": {
                    "LONG": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                    "SHORT": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                },
                "by_timeframe": {
                    "5m": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                    "15m": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                    "60m": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
                },
            }

        outcome_counts = {"OPEN": 0, "T1": 0, "T2": 0, "SL": 0, "EXPIRED": 0}
        by_grade = {
            "A+": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
            "A": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
            "B": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
        }
        by_action = {
            "LONG": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
            "SHORT": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
        }
        by_timeframe: Dict[str, Dict[str, Any]] = {}
        rr_list: List[float] = []

        closed_wins = 0
        closed_losses = 0

        for s in signals:
            outcome = s["outcome"]
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            eff_rr = s.get("rr") if s.get("rr") is not None else s.get("shadow_rr")
            if eff_rr is not None and eff_rr > 0:
                rr_list.append(float(eff_rr))

            is_win = outcome in ("T1", "T2")
            is_loss = outcome == "SL"
            if is_win:
                closed_wins += 1
            elif is_loss:
                closed_losses += 1

            grade = s.get("grade", "C")
            if grade in by_grade:
                by_grade[grade]["total"] += 1
                if is_win:
                    by_grade[grade]["wins"] += 1
                elif is_loss:
                    by_grade[grade]["losses"] += 1

            act = "LONG" if "LONG" in s.get("action", "").upper() else "SHORT"
            if act in by_action:
                by_action[act]["total"] += 1
                if is_win:
                    by_action[act]["wins"] += 1
                elif is_loss:
                    by_action[act]["losses"] += 1

            tf_key = f"{s.get('timeframe', 5)}m"
            if tf_key not in by_timeframe:
                by_timeframe[tf_key] = {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0}
            by_timeframe[tf_key]["total"] += 1
            if is_win:
                by_timeframe[tf_key]["wins"] += 1
            elif is_loss:
                by_timeframe[tf_key]["losses"] += 1

        total_closed = closed_wins + closed_losses
        overall_win_rate = round((closed_wins / total_closed * 100.0), 1) if total_closed > 0 else 0.0

        for g, data in by_grade.items():
            tot_cl = data["wins"] + data["losses"]
            data["win_rate"] = round((data["wins"] / tot_cl * 100.0), 1) if tot_cl > 0 else 0.0

        for a, data in by_action.items():
            tot_cl = data["wins"] + data["losses"]
            data["win_rate"] = round((data["wins"] / tot_cl * 100.0), 1) if tot_cl > 0 else 0.0

        for t, data in by_timeframe.items():
            tot_cl = data["wins"] + data["losses"]
            data["win_rate"] = round((data["wins"] / tot_cl * 100.0), 1) if tot_cl > 0 else 0.0

        avg_rr = round(sum(rr_list) / len(rr_list), 2) if rr_list else 0.0

        return {
            "total_signals": total,
            "win_rate_pct": overall_win_rate,
            "average_rr": avg_rr,
            "outcomes": outcome_counts,
            "by_grade": by_grade,
            "by_action": by_action,
            "by_timeframe": by_timeframe,
        }

    def get_signal_stats(self, include_gated: bool = False) -> Dict[str, Any]:
        """Aggregate performance and win rate metrics across logged signals.
        When include_gated=True, compares ungated vs gated setups side-by-side."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM signals")
            all_signals = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        ungated_signals = [s for s in all_signals if not s.get("gated")]
        gated_signals = [s for s in all_signals if s.get("gated")]

        stats = self._calc_subset_stats(ungated_signals)
        if include_gated:
            gated_stats = self._calc_subset_stats(gated_signals)
            stats["comparison"] = {
                "ungated": {
                    "total_signals": len(ungated_signals),
                    "win_rate_pct": stats["win_rate_pct"],
                    "average_rr": stats["average_rr"],
                    "outcomes": stats["outcomes"],
                },
                "gated": {
                    "total_signals": len(gated_signals),
                    "win_rate_pct": gated_stats["win_rate_pct"],
                    "average_rr": gated_stats["average_rr"],
                    "outcomes": gated_stats["outcomes"],
                },
            }
        return stats
