/* QuantFlow — Unified API Layer */

const QFApi = (() => {
  const PLATFORM = '/api/platform';
  const _inflight = new Map();

  function headers(extra = {}) {
    const h = { ...extra };
    const key = sessionStorage.getItem('dashboard_api_key');
    if (key) h['X-Dashboard-Api-Key'] = key;
    return h;
  }

  async function request(url, opts = {}) {
    opts.headers = headers(opts.headers || {});
    const isGet = !opts.method || opts.method === 'GET';
    const key = isGet ? url : `${opts.method}:${url}`;

    if (isGet) {
      _inflight.get(key)?.abort();
      const ctrl = new AbortController();
      _inflight.set(key, ctrl);
      const tid = setTimeout(() => ctrl.abort(), 12000);
      try {
        const res = await fetch(url, { ...opts, signal: ctrl.signal });
        clearTimeout(tid);
        _inflight.delete(key);
        if (!res.ok) {
          let body = {};
          try { body = await res.json(); } catch (_) {}
          const err = new Error(body.error || `HTTP ${res.status}`);
          err.code = body.error_code || 'HTTP_ERROR';
          throw err;
        }
        return res.json();
      } catch (e) {
        clearTimeout(tid);
        _inflight.delete(key);
        if (e.name === 'AbortError') throw Object.assign(new Error('Таймаут'), { code: 'TIMEOUT' });
        throw e;
      }
    }

    const res = await fetch(url, opts);
    if (!res.ok) {
      let body = {};
      try { body = await res.json(); } catch (_) {}
      throw new Error(body.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  return {
    request,
    headers,
    overview: () => request(`${PLATFORM}/overview`),
    portfolio: (mode = 'rub') => request(`${PLATFORM}/portfolio?mode=${mode}`),
    positions: () => request(`${PLATFORM}/portfolio/positions`),
    paperAccount: (mode = 'rub') => request(`${PLATFORM}/paper/account?mode=${mode}`),
    signals: (params = {}) => {
      const q = new URLSearchParams(params);
      return request(`${PLATFORM}/signals?${q}`);
    },
    generateSignals: () => request(`${PLATFORM}/signals/generate`, { method: 'POST' }),
    executeSignal: (id) => request(`${PLATFORM}/signals/${id}/execute`, { method: 'POST' }),
    stats: () => request('/api/stats'),
    equity: () => request('/api/equity'),
    log: () => request('/api/log'),
    marketQuotes: () => request('/api/portfolio'),
    candles: (ticker, limit = 120) => request(`/api/candles?ticker=${ticker}&limit=${limit}`),
    settings: () => request('/api/settings'),
    tinkoffPositions: () => request('/api/tinkoff/positions'),
    backtestRun: (body) => request(`${PLATFORM}/backtest/run`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    }),
    backtestRuns: () => request(`${PLATFORM}/backtest/runs`),
    closePosition: (positionId, mode = 'rub') => request(`${PLATFORM}/paper/trade`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ action: 'close', position_id: positionId, mode }),
    }),
    analytics() { return request('/api/platform/analytics'); },
    engineStatus() { return request('/api/platform/engine/status'); },
    engineStart() { return request('/api/platform/engine/start', { method: 'POST' }); },
    engineStop() { return request('/api/platform/engine/stop', { method: 'POST' }); },
    paperTrades(limit = 50) { return request(`/api/platform/paper/trades?limit=${limit}`); },
    closePaperPosition(posId, reason = 'manual') {
      return request(`/api/platform/paper/position/${posId}/close`, {
        method: 'POST', headers: headers({'Content-Type': 'application/json'}), body: JSON.stringify({ reason })
      });
    },
  };
})();

window.QFApi = QFApi;
window.fetchJSON = QFApi.request;
window.dashboardApiHeaders = QFApi.headers;