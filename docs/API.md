# Zien Quant - REST API Specification

This document provides complete documentation for the Zien Quant HTTP REST API, including authentication requirements, request schemas, response formats, and error codes.

---

## 1. Authentication & Security Model

- **Session Authentication**: Managed via HTTP-Only, SameSite=Strict cookies (`session_id`).
- **CSRF Token**: All mutating requests (`POST`, `PUT`, `DELETE`) require the `X-CSRF-Token` header. The token is obtained via `/api/bootstrap`.
- **Rate Limits**:
  - Global: 120 requests/minute per client IP.
  - LLM Endpoints (`/api/ai/pulse`, `/api/ai/chat`, `/api/ai/analyze`): 6 requests/minute.
  - Export: 5 requests/minute.
  - Tracking: 10 requests/minute.
- **Payload Cap**: Max 64 KB per POST body (returns HTTP 413 if exceeded).

---

## 2. Public & Market Endpoints

### 2.1 GET `/api/flow`
Returns the complete flow river layout, 4-stage funnel symbols, and verified R:R-gated setup cards. Supports automatic Gzip compression.

**Query Parameters:**
- `timeframe` (optional, default `5m`): Intraday timeframe (`1m`, `5m`, `15m`).
- `limit` (optional, default `100`): Maximum symbols in response.

**Response `200 OK`:**
```json
{
  "timestamp": 1792980000,
  "session_state": "LIVE",
  "is_previous_session": false,
  "target_session_date": "2026-10-26",
  "river": [
    {
      "symbol": "RELIANCE",
      "company_name": "Reliance Industries Ltd",
      "sector": "Energy",
      "current_price": 2845.50,
      "change_pct": 1.42,
      "score": 78.5,
      "stage": "Breakout",
      "stream_path": [
        {"bar_index": 0, "pct_from_open": 0.0, "price": 2805.0},
        {"bar_index": 74, "pct_from_open": 1.42, "price": 2845.50}
      ]
    }
  ],
  "funnel": {
    "accumulation": ["TCS", "INFY"],
    "absorption": ["HDFCBANK"],
    "breakout": ["RELIANCE", "SBIN"],
    "retest": ["ICICIBANK"]
  },
  "setup_cards": [
    {
      "symbol": "RELIANCE",
      "signal_type": "BUY",
      "stage": "Breakout",
      "conviction_score": 78.5,
      "entry_price": 2845.50,
      "stop_loss": 2815.00,
      "target_price": 2910.00,
      "rr_ratio": 2.11,
      "order_block_zone": [2820.00, 2835.00],
      "invalidation_level": 2815.00,
      "source": "rules_engine"
    }
  ]
}
```

### 2.2 GET `/api/market`
Returns current market breadth, sector allocations, and top conviction rankings.

### 2.3 GET `/api/market/schedule`
Returns the operational state of the Indian National Stock Exchange (NSE).
```json
{
  "state": "CLOSED",
  "is_open": false,
  "label": "Market Closed (Pre-Market)",
  "target_time_ist": "2026-10-26 09:15:00 IST",
  "remaining_seconds": 8508,
  "countdown_formatted": "02h 21m 48s"
}
```

### 2.4 GET `/api/health`
Health probe for uptime monitoring, load balancers, and process watchdogs.
```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_sec": 1420.5,
  "database": "connected",
  "session_state": "CLOSED"
}
```

### 2.5 GET `/api/stocks/database`
Searches the 2,600+ equities in the local stock master catalog.
**Query Parameters:**
- `q`: Symbol prefix, substring, or company name (e.g. `RELIANCE` or `TATA`).

---

## 3. Laya AI Intelligence Endpoints

### 3.1 GET `/api/ai/status`
Returns Ollama connection health, loaded model status, and recent latency telemetry.
```json
{
  "reachable": true,
  "model": "gemma4:12b",
  "model_loaded": true,
  "avg_latency_ms": 342.1,
  "queue_depth": 0
}
```

### 3.2 GET / POST `/api/ai/analyze`
Requests deep quantitative and structural analysis for a specific symbol.
**Parameters:**
- `symbol`: Equity ticker symbol (e.g. `RELIANCE`).

**Response `200 OK`:**
```json
{
  "symbol": "RELIANCE",
  "source": "local_llm",
  "model": "gemma4:12b",
  "signal_type": "BUY",
  "score": 78.5,
  "commentary": "Volume expansion confirmed above 2830 level. Technical breakout targeting 2910 resistance with 2.11 R:R ratio.",
  "validated": true,
  "latency_ms": 420.5
}
```

---

## 4. Administrative & Owner Endpoints

All administrative endpoints require an active session belonging to the `owner` role.

### 4.1 POST `/api/login`
Authenticates a user and establishes a session cookie.
```json
{
  "email": "owner@example.com",
  "password": "StrongPassword123!",
  "totp_token": "123456"
}
```

### 4.2 POST `/api/logout`
Destroys the current user session and expires the session cookie.

### 4.3 GET `/api/admin`
Retrieves system diagnostics, active user sessions, and hardware telemetry.

### 4.4 POST `/api/config`
Updates runtime quantitative and scraper thresholds. Requires `X-CSRF-Token`.

### 4.5 POST `/api/backup`
Triggers an immediate ACID-safe SQLite database backup to `work/backups/`.
