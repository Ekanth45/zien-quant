"""Read-only historical candles from the user's FYERS market-data API."""
from __future__ import annotations

import csv
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import date, datetime, time as day_time, timedelta, timezone
from pathlib import Path
from typing import Any


IST = timezone(timedelta(hours=5, minutes=30))
MIN_HISTORY_DATE = date(2023, 5, 6)
FYERS_HISTORY_URL = "https://api-t1.fyers.in/data/history"
FYERS_NSE_MASTER_URL = "https://public.fyers.in/sym_details/NSE_CM.csv"
RESOLUTIONS = {"1", "2", "3", "5", "10", "15", "20", "30", "45", "60", "120", "180", "240", "D"}
_CACHE_TTL_SECONDS = 600


class FyersHistoryError(Exception):
    """Safe, user-presentable error from the FYERS history provider."""


class FyersHistoryNotConfigured(FyersHistoryError):
    pass


class FyersHistoryAuthError(FyersHistoryError):
    pass


class FyersHistoryRateLimitError(FyersHistoryError):
    pass


class FyersHistoryProvider:
    """Fetch candles and NSE instrument symbols without exposing broker tokens."""

    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = runtime_dir or Path(__file__).resolve().parent.parent / "work" / "runtime"
        self.master_path = self.runtime_dir / "fyers_nse_cm.csv"
        self._lock = threading.RLock()
        self._master: list[dict[str, str]] | None = None
        self._master_loaded_at = 0.0
        self._last_request_at = 0.0
        self._history_cache: OrderedDict[tuple[str, str, str, str], tuple[float, list[dict[str, Any]]]] = OrderedDict()

    @staticmethod
    def credentials_configured() -> bool:
        app_id = os.environ.get("FYERS_APP_ID") or os.environ.get("FYERS_CLIENT_ID")
        token = os.environ.get("FYERS_ACCESS_TOKEN")
        return bool(app_id and token)

    @staticmethod
    def _credentials() -> tuple[str, str]:
        app_id = (os.environ.get("FYERS_APP_ID") or os.environ.get("FYERS_CLIENT_ID") or "").strip()
        token = (os.environ.get("FYERS_ACCESS_TOKEN") or "").strip()
        if not app_id or not token:
            raise FyersHistoryNotConfigured(
                "Connect FYERS market data by setting FYERS_APP_ID and FYERS_ACCESS_TOKEN in the server's .env file."
            )
        return app_id, token

    def _read_master(self, content: str) -> list[dict[str, str]]:
        instruments: list[dict[str, str]] = []
        for row in csv.reader(content.splitlines()):
            # FYERS's headerless master has had a blank expiry-date column
            # inserted over time. Locate the exact ticker cell and use the
            # short-symbol field four columns after it (current and older files).
            ticker_index = next((index for index, value in enumerate(row) if value.strip().upper().startswith("NSE:")), None)
            if ticker_index is None:
                continue
            ticker = row[ticker_index].strip().upper()
            instrument_type = row[2].strip()
            if not ticker.startswith("NSE:") or instrument_type not in {"0", "10"}:
                continue
            short_symbol = row[ticker_index + 4].strip().upper() if len(row) > ticker_index + 4 else ""
            short_symbol = short_symbol or ticker.split(":", 1)[-1].split("-", 1)[0]
            instruments.append({
                "symbol": ticker,
                "short_symbol": short_symbol,
                "name": row[1].strip() or short_symbol,
                "kind": "index" if instrument_type == "10" else "equity",
            })
        if not instruments:
            raise FyersHistoryError("FYERS returned an unrecognized NSE symbol master.")
        return instruments

    def _load_symbol_master(self, force: bool = False) -> list[dict[str, str]]:
        now = time.time()
        with self._lock:
            if self._master and not force and now - self._master_loaded_at < 86400:
                return self._master
            cached_text = None
            if self.master_path.exists() and not force:
                try:
                    if now - self.master_path.stat().st_mtime < 86400:
                        cached_text = self.master_path.read_text(encoding="utf-8")
                except OSError:
                    cached_text = None
        if cached_text is None:
            try:
                request = urllib.request.Request(
                    FYERS_NSE_MASTER_URL,
                    headers={"User-Agent": "ZienQuant/1.0", "Accept": "text/csv"},
                )
                with urllib.request.urlopen(request, timeout=12) as response:
                    cached_text = response.read(16 * 1024 * 1024 + 1).decode("utf-8", errors="replace")
                if len(cached_text) > 16 * 1024 * 1024:
                    raise FyersHistoryError("FYERS symbol master exceeded the size limit.")
                instruments = self._read_master(cached_text)
                try:
                    self.runtime_dir.mkdir(parents=True, exist_ok=True)
                    temporary = self.master_path.with_suffix(".csv.tmp")
                    temporary.write_text(cached_text, encoding="utf-8")
                    temporary.replace(self.master_path)
                except OSError:
                    pass
            except FyersHistoryError:
                raise
            except Exception as exc:
                # Use the last verified daily master if the provider is briefly
                # unavailable; never invent symbol suffixes.
                try:
                    cached_text = self.master_path.read_text(encoding="utf-8")
                    instruments = self._read_master(cached_text)
                except Exception:
                    raise FyersHistoryError("FYERS symbol search is unavailable right now.") from exc
        else:
            instruments = self._read_master(cached_text)
        with self._lock:
            self._master = instruments
            self._master_loaded_at = now
        return instruments

    def search_instruments(self, query: str, limit: int = 15) -> dict[str, Any]:
        clean = " ".join(str(query or "").strip().upper().split())[:80]
        if not clean:
            return {"instruments": [], "source": "FYERS NSE Symbol Master"}
        terms = [term for term in clean.replace(":", " ").replace("-", " ").split() if term]
        instruments = self._load_symbol_master()
        ranked: list[tuple[int, dict[str, str]]] = []
        for instrument in instruments:
            short = instrument["short_symbol"]
            ticker = instrument["symbol"]
            name = instrument["name"].upper()
            searchable = f"{short} {ticker} {name}"
            if clean == short or clean == ticker:
                rank = 0
            elif short.startswith(clean) or ticker.split(":", 1)[-1].startswith(clean):
                rank = 1
            elif all(term in searchable for term in terms):
                rank = 2
            elif clean in name:
                rank = 3
            else:
                continue
            ranked.append((rank, instrument))
        ranked.sort(key=lambda item: (item[0], item[1]["kind"] != "equity", item[1]["short_symbol"]))
        return {
            "instruments": [item for _, item in ranked[:max(1, min(25, int(limit)))]],
            "source": "FYERS NSE Symbol Master",
            "master_updated_at": datetime.fromtimestamp(self.master_path.stat().st_mtime, IST).isoformat() if self.master_path.exists() else None,
        }

    def _request_chunk(self, symbol: str, resolution: str, start: date, end: date) -> list[dict[str, Any]]:
        app_id, access_token = self._credentials()
        from_dt = datetime.combine(start, day_time.min, IST)
        to_dt = datetime.combine(end, day_time.max, IST)
        if resolution != "D" and end == datetime.now(IST).date():
            interval = int(resolution)
            to_dt = min(to_dt, datetime.now(IST) - timedelta(minutes=interval))
        if to_dt < from_dt:
            return []
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "0",
            "range_from": str(int(from_dt.timestamp())),
            "range_to": str(int(to_dt.timestamp())),
            "cont_flag": "1",
        })
        request = urllib.request.Request(
            f"{FYERS_HISTORY_URL}?{params}",
            headers={"Authorization": f"{app_id}:{access_token}", "Accept": "application/json", "User-Agent": "ZienQuant/1.0"},
        )
        # Stay below FYERS Standard's documented data API limit of 5 req/sec.
        with self._lock:
            wait_for = 0.22 - (time.monotonic() - self._last_request_at)
        if wait_for > 0:
            time.sleep(wait_for)
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                payload = json.loads(response.read().decode("utf-8"))
            with self._lock:
                self._last_request_at = time.monotonic()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise FyersHistoryAuthError("FYERS rejected the access token or the app lacks market-data permission.") from exc
            if exc.code == 429:
                raise FyersHistoryRateLimitError("FYERS data request limit reached. Wait a moment and try again.") from exc
            raise FyersHistoryError(f"FYERS historical data request failed (HTTP {exc.code}).") from exc
        except FyersHistoryError:
            raise
        except Exception as exc:
            raise FyersHistoryError("Could not reach the FYERS historical-data service.") from exc

        if payload.get("s") != "ok":
            code = str(payload.get("code", ""))
            message = str(payload.get("message", "")).casefold()
            if code in {"-300", "-5"} and "symbol" in message:
                raise FyersHistoryError("FYERS does not recognize this instrument symbol.")
            if "no data" in message or "no_data" in message or code in {"-16", "-17"}:
                return []
            raise FyersHistoryError("FYERS could not return historical candles for this range.")

        candles: list[dict[str, Any]] = []
        for raw in payload.get("candles", []):
            if not isinstance(raw, (list, tuple)) or len(raw) < 5:
                continue
            try:
                timestamp, opening, high, low, close = raw[:5]
                volume = raw[5] if len(raw) > 5 else None
                candle = {"t": int(timestamp), "o": float(opening), "h": float(high), "l": float(low), "c": float(close), "closed": True}
                if volume is not None:
                    candle["v"] = float(volume)
                candles.append(candle)
            except (TypeError, ValueError, OverflowError):
                continue
        return candles

    def get_candles(self, symbol: str, start: str, end: str, resolution: str) -> dict[str, Any]:
        resolution = str(resolution).upper()
        if resolution not in RESOLUTIONS:
            raise FyersHistoryError("Choose a candle interval supported by FYERS.")
        try:
            start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        except (TypeError, ValueError) as exc:
            raise FyersHistoryError("Enter valid dates in YYYY-MM-DD format.") from exc
        today = datetime.now(IST).date()
        if start_date < MIN_HISTORY_DATE:
            raise FyersHistoryError("The chart history starts on 6 May 2023.")
        if end_date > today or start_date > end_date:
            raise FyersHistoryError("Choose a date range from 6 May 2023 through today.")
        if not re_full_fyers_symbol(symbol):
            raise FyersHistoryError("Choose an NSE instrument from the search results.")
        app_id, _ = self._credentials()
        known = {row["symbol"] for row in self._load_symbol_master()}
        symbol = str(symbol).upper()
        if symbol not in known:
            raise FyersHistoryError("Choose an instrument listed in the current FYERS NSE symbol master.")

        cache_key = (symbol, resolution, start_date.isoformat(), end_date.isoformat())
        now = time.monotonic()
        with self._lock:
            cached = self._history_cache.get(cache_key)
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                self._history_cache.move_to_end(cache_key)
                candles = [dict(item) for item in cached[1]]
                return self._payload(symbol, resolution, start_date, end_date, candles)
        del app_id

        chunk_days = 366 if resolution == "D" else 100
        rows: dict[int, dict[str, Any]] = {}
        cursor = start_date
        while cursor <= end_date:
            chunk_end = min(end_date, cursor + timedelta(days=chunk_days - 1))
            for candle in self._request_chunk(symbol, resolution, cursor, chunk_end):
                if start_date <= datetime.fromtimestamp(candle["t"], IST).date() <= end_date:
                    rows[candle["t"]] = candle
            cursor = chunk_end + timedelta(days=1)
        candles = [rows[key] for key in sorted(rows)]
        with self._lock:
            self._history_cache[cache_key] = (time.monotonic(), [dict(item) for item in candles])
            self._history_cache.move_to_end(cache_key)
            while len(self._history_cache) > 64:
                self._history_cache.popitem(last=False)
        return self._payload(symbol, resolution, start_date, end_date, candles)

    @staticmethod
    def _payload(symbol: str, resolution: str, start: date, end: date, candles: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "resolution": resolution,
            "range_from": start.isoformat(),
            "range_to": end.isoformat(),
            "candles": candles,
            "count": len(candles),
            "latest_timestamp": candles[-1]["t"] if candles else None,
            "data_source": "FYERS Historical Data API",
            "streaming": False,
            "delay_status": "Historical data; not a live stream",
        }


def re_full_fyers_symbol(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"NSE:[A-Z0-9&._-]{1,40}", str(value or "").upper()))


_provider: FyersHistoryProvider | None = None
_provider_lock = threading.Lock()


def get_fyers_history_provider() -> FyersHistoryProvider:
    global _provider
    with _provider_lock:
        if _provider is None:
            _provider = FyersHistoryProvider()
        return _provider
