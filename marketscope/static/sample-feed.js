/**
 * MarketScope Client API Interface
 * Communicates directly with MarketScope Python backend HTTP services.
 * Pure real-time and historical session data only; zero simulated fallback.
 */

export class PublicFeedAdapter {
  constructor() {
    this.hasBackend = null;
  }

  async checkBackend() {
    if (this.hasBackend !== null) return this.hasBackend;
    try {
      const res = await fetch('/api/bootstrap', { method: 'GET', cache: 'no-cache' });
      if (res.ok) {
        this.hasBackend = true;
        return true;
      }
    } catch {
      // Backend not reached
    }
    this.hasBackend = false;
    return false;
  }

  async getBootstrap() {
    try {
      const res = await fetch('/api/bootstrap');
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Failed to fetch bootstrap:', err);
    }
    return {
      config: {
        brand_name: 'MarketScope',
        tagline: 'NSE Flow Terminal & Directional Intelligence',
        default_timeframe: 5,
        refresh_interval_ms: 2000,
      },
      has_owner: false,
      catalogue: {},
      session: { authenticated: false, email: null, role: null, csrf_token: null },
      provider_status: {
        live_available: false,
        reason: 'Backend service unreachable',
      },
    };
  }

  async getMarketSnapshot(mode = 'live', timeframe = 5, session = null) {
    try {
      let url = `/api/market?timeframe=${encodeURIComponent(timeframe)}`;
      if (session) {
        url += `&session=${encodeURIComponent(session)}`;
      }
      const res = await fetch(url);
      if (res.ok) return await res.json();
      if (res.status === 503) {
        const errData = await res.json().catch(() => ({}));
        return { error: 'feed_unavailable', status: 503, detail: errData.detail || 'Live feed unavailable' };
      }
      return { error: 'http_error', status: res.status };
    } catch (err) {
      return { error: 'feed_unavailable', status: 503, detail: err.message };
    }
  }

  async getStockCandles(symbol, timeframe = 5) {
    try {
      const res = await fetch(`/api/stock?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`);
      if (res.ok) return await res.json();
      return { error: 'candles_unavailable', status: res.status, candles: [] };
    } catch (err) {
      return { error: 'network_error', detail: err.message, candles: [] };
    }
  }

  async getSessionSummary(dateStr = null) {
    try {
      let url = '/api/session/summary';
      if (dateStr) {
        url += `?date=${encodeURIComponent(dateStr)}`;
      }
      const res = await fetch(url);
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      return { error: err.error || 'session_not_found', detail: err.detail || 'Session summary unavailable', status: res.status };
    } catch (err) {
      return { error: 'network_error', detail: err.message, status: 503 };
    }
  }

  async getAIPulse(refresh = false) {
    try {
      const url = `/api/ai/pulse${refresh ? '?refresh=1' : ''}`;
      const res = await fetch(url);
      if (res.ok) return await res.json();
      return { error: 'pulse_unavailable', status: res.status };
    } catch (err) {
      return { error: 'network_error', detail: err.message };
    }
  }

  async getAIAnalyze(symbol, timeframe = 5, refresh = false, poll = false) {
    try {
      const params = new URLSearchParams({
        symbol: symbol,
        timeframe: timeframe.toString(),
      });
      if (refresh) params.append('refresh', '1');
      if (poll) params.append('poll', '1');

      const res = await fetch(`/api/ai/analyze?${params.toString()}`);
      if (res.ok) return await res.json();
      return { error: 'analysis_unavailable', status: res.status };
    } catch (err) {
      return { error: 'network_error', detail: err.message };
    }
  }

  async sendAIChat(message, symbol = null) {
    try {
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, symbol }),
      });
      return await res.json();
    } catch (err) {
      return { error: 'chat_network_error', detail: err.message };
    }
  }

  async searchStockDatabase(query, exchange = 'ALL', limit = 12) {
    try {
      const res = await fetch(`/api/stocks/database?q=${encodeURIComponent(query)}&exchange=${encodeURIComponent(exchange)}&limit=${limit}`);
      if (res.ok) return await res.json();
      return { stocks: [], total_matches: 0 };
    } catch (err) {
      return { stocks: [], total_matches: 0, error: err.message };
    }
  }

  async trackStock(symbol) {
    try {
      const res = await fetch('/api/stocks/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      return await res.json();
    } catch (err) {
      return { error: err.message };
    }
  }

  async untrackStock(symbol) {
    try {
      const res = await fetch('/api/stocks/untrack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      return await res.json();
    } catch (err) {
      return { error: err.message };
    }
  }
}

export const publicAPI = new PublicFeedAdapter();
