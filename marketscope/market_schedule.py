"""
MarketScope NSE & BSE Trading Schedule & Countdown Engine
Provides real-time market session detection, accurate opening/closing schedules,
and precise millisecond/second countdown calculations for Indian Equities.
"""

from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, Any, Optional, Set, Tuple

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Standard NSE & BSE Trading Timings (IST)
TIME_PRE_OPEN_START = time(9, 0, 0)
TIME_MARKET_OPEN = time(9, 15, 0)
TIME_MARKET_CLOSE = time(15, 30, 0)
TIME_POST_CLOSE_END = time(16, 0, 0)

# Declared Indian Exchange Trading Holidays (Year, Month, Day)
# Covers standard annual exchange closures (Republic Day, Holi, Good Friday, Ambedkar Jayanti,
# Maharashtra Day, Independence Day, Gandhi Jayanti, Dussehra, Diwali, Gurunanak Jayanti, Christmas)
EXCHANGE_HOLIDAYS: Set[Tuple[int, int, int]] = {
    # 2025 Holidays
    (2025, 1, 26), (2025, 2, 26), (2025, 3, 14), (2025, 3, 31),
    (2025, 4, 10), (2025, 4, 14), (2025, 4, 18), (2025, 5, 1),
    (2025, 8, 15), (2025, 8, 27), (2025, 10, 2), (2025, 10, 21),
    (2025, 11, 5), (2025, 12, 25),
    # 2026 Holidays
    (2026, 1, 26), (2026, 3, 3), (2026, 3, 20), (2026, 4, 3),
    (2026, 4, 14), (2026, 5, 1), (2026, 5, 27), (2026, 6, 26),
    (2026, 8, 15), (2026, 10, 2), (2026, 10, 20), (2026, 11, 8),
    (2026, 11, 9), (2026, 11, 24), (2026, 12, 25),
    # 2027 Holidays
    (2027, 1, 26), (2027, 3, 22), (2027, 3, 26), (2027, 4, 14),
    (2027, 5, 1), (2027, 8, 15), (2027, 10, 2), (2027, 10, 20),
    (2027, 11, 10), (2027, 12, 25)
}


def is_market_holiday(d: date) -> bool:
    """Returns True if the given date is a declared exchange holiday."""
    return (d.year, d.month, d.day) in EXCHANGE_HOLIDAYS


def is_trading_day(d: date) -> bool:
    """Returns True if the given date is a weekday and not an exchange holiday."""
    if d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False
    return not is_market_holiday(d)


def get_next_trading_day(start_date: date) -> date:
    """Advances from start_date forward until the next open trading business day is found."""
    current = start_date
    while not is_trading_day(current):
        current += timedelta(days=1)
    return current


def format_countdown_string(total_seconds: int) -> str:
    """
    Formats remaining seconds into a clear human-readable countdown string.
    Examples:
        - 45 seconds -> "00h 00m 45s"
        - 3720 seconds -> "01h 02m 00s"
        - 131400 seconds (1.5 days) -> "1d 12h 30m 00s"
    """
    total_seconds = max(0, int(total_seconds))
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


def get_market_schedule_info(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates detailed market schedule state and countdown for NSE & BSE.
    If dt is None, uses current system time normalized to IST.
    """
    if dt is None:
        dt = datetime.now(IST)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    today = dt.date()
    current_time = dt.time()
    weekday = dt.weekday()
    holiday = is_market_holiday(today)
    weekend = weekday >= 5

    # Determine current session status and next target transition
    if not weekend and not holiday:
        # Weekday regular trading calendar
        if current_time < TIME_PRE_OPEN_START:
            # 00:00 - 08:59:59 IST
            state = "CLOSED"
            status_badge = "CLOSED"
            label = "Market Closed (Pre-Market)"
            target_dt = datetime.combine(today, TIME_MARKET_OPEN, tzinfo=IST)
            action = "opens"
            is_open = False
            session_description = "Pre-market order collection begins at 09:00 IST. Normal trading begins at 09:15 IST."

        elif TIME_PRE_OPEN_START <= current_time < TIME_MARKET_OPEN:
            # 09:00 - 09:14:59 IST
            state = "PRE_OPEN"
            status_badge = "PRE-OPEN"
            label = "Pre-Open Session (NSE & BSE)"
            target_dt = datetime.combine(today, TIME_MARKET_OPEN, tzinfo=IST)
            action = "opens"
            is_open = False
            session_description = "Pre-market order collection & price discovery in progress. Normal trading opens at 09:15 IST."

        elif TIME_MARKET_OPEN <= current_time < TIME_MARKET_CLOSE:
            # 09:15 - 15:30:00 IST
            state = "OPEN"
            status_badge = "LIVE OPEN"
            label = "Market Open (NSE & BSE)"
            target_dt = datetime.combine(today, TIME_MARKET_CLOSE, tzinfo=IST)
            action = "closes"
            is_open = True
            session_description = "Regular trading session is actively underway until 15:30 IST."

        elif TIME_MARKET_CLOSE <= current_time < TIME_POST_CLOSE_END:
            # 15:30 - 16:00:00 IST
            state = "POST_CLOSE"
            status_badge = "POST-CLOSE"
            label = "Post-Closing Session"
            next_trade_day = get_next_trading_day(today + timedelta(days=1))
            target_dt = datetime.combine(next_trade_day, TIME_MARKET_OPEN, tzinfo=IST)
            action = "opens"
            is_open = False
            session_description = "Closing price settlement and post-market trading. Next regular session opens tomorrow at 09:15 IST."

        else:
            # 16:00 - 23:59:59 IST
            state = "CLOSED"
            status_badge = "CLOSED"
            label = "Market Closed (After Hours)"
            next_trade_day = get_next_trading_day(today + timedelta(days=1))
            target_dt = datetime.combine(next_trade_day, TIME_MARKET_OPEN, tzinfo=IST)
            action = "opens"
            is_open = False
            session_description = f"Exchange closed for the day. Next regular session opens {next_trade_day.strftime('%A, %b %d')} at 09:15 IST."

    else:
        # Weekend or Official Exchange Holiday
        state = "WEEKEND" if weekend else "HOLIDAY"
        status_badge = "WEEKEND" if weekend else "HOLIDAY"
        label = "Weekend Closed" if weekend else "Exchange Holiday Closed"
        next_trade_day = get_next_trading_day(today + timedelta(days=1))
        target_dt = datetime.combine(next_trade_day, TIME_MARKET_OPEN, tzinfo=IST)
        action = "opens"
        is_open = False
        session_description = f"Exchange closed ({'Weekend' if weekend else 'Declared Holiday'}). Next regular session opens {next_trade_day.strftime('%A, %b %d')} at 09:15 IST."

    # Compute remaining time delta
    diff = target_dt - dt
    total_seconds = max(0, int(diff.total_seconds()))
    countdown_str = format_countdown_string(total_seconds)

    target_phrase = f"{action.capitalize()} in {countdown_str}"

    return {
        "is_open": is_open,
        "state": state,
        "status_badge": status_badge,
        "label": label,
        "action": action,
        "target_timestamp": int(target_dt.timestamp()),
        "target_time_ist": target_dt.strftime("%Y-%m-%d %H:%M:%S IST"),
        "target_time_iso": target_dt.isoformat(),
        "target_day_name": target_dt.strftime("%A, %b %d"),
        "current_time_ist": dt.strftime("%H:%M:%S IST"),
        "current_date_ist": dt.strftime("%Y-%m-%d"),
        "current_timestamp": int(dt.timestamp()),
        "remaining_seconds": total_seconds,
        "countdown_formatted": countdown_str,
        "phrase": target_phrase,
        "session_description": session_description,
        "exchange_hours": {
            "pre_open": "09:00 - 09:15 IST",
            "normal_trading": "09:15 - 15:30 IST",
            "post_close": "15:30 - 16:00 IST",
            "timezone": "IST (UTC+05:30)",
        }
    }
