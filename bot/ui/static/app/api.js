/**
 * The API client. One place that knows about the envelope, CSRF and abortion.
 *
 * The layer it replaces had a 12-second hard abort while a full sync batch spanned
 * 13 seconds, so the client routinely cancelled its own in-flight requests — and
 * it treated a rejected slice as absent rather than as failed.
 *
 * Contract handled here, not by each caller:
 *   success → `{data, meta}`   → resolves to `{data, meta}`
 *   failure → `{error:{code,message,id}}` → throws `ApiError`
 *
 * The CSRF token comes from the session and is echoed in a header. It is read from
 * the readable cookie rather than embedded in the page, so it stays correct after a
 * session refresh without a reload.
 */

const CSRF_COOKIE = 'qf_csrf';
const CSRF_HEADER = 'X-CSRF-Token';
const IDEMPOTENCY_HEADER = 'X-Idempotency-Key';

/** A failure that carries the contract's code and correlation id. */
export class ApiError extends Error {
  constructor({ code, message, id, status }) {
    super(message || 'Ошибка запроса');
    this.name = 'ApiError';
    this.code = code || 'INTERNAL';
    this.correlationId = id || null;
    this.status = status || 0;
  }

  /** Whether retrying unchanged could plausibly succeed. */
  get retryable() {
    return ['DB_UNAVAILABLE', 'BROKER_UNAVAILABLE', 'UPSTREAM_TIMEOUT', 'INTERNAL']
      .includes(this.code);
  }

  /** Whether the UI should send the operator to the sign-in surface. */
  get needsAuth() {
    return this.code === 'UNAUTHENTICATED';
  }
}

function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function csrfToken() {
  return readCookie(CSRF_COOKIE);
}

/**
 * Per-key abort controllers.
 *
 * A view switch must cancel that view's in-flight requests, or a slow response
 * from the screen the operator just left will overwrite the one they are looking
 * at. Keyed rather than global so two slices can be in flight together.
 */
const inflight = new Map();

function controllerFor(key) {
  if (!key) return null;
  abort(key);
  const controller = new AbortController();
  inflight.set(key, controller);
  return controller;
}

export function abort(key) {
  const existing = inflight.get(key);
  if (existing) {
    existing.abort();
    inflight.delete(key);
  }
}

export function abortAll(prefix = '') {
  for (const key of Array.from(inflight.keys())) {
    if (!prefix || key.startsWith(prefix)) abort(key);
  }
}

/** Thrown when the caller aborted; distinguishable from a real failure. */
export class AbortedError extends Error {
  constructor() {
    super('Запрос отменён');
    this.name = 'AbortedError';
    this.aborted = true;
  }
}

async function request(method, path, { body, key, timeout = 20000, idempotencyKey } = {}) {
  const controller = controllerFor(key) || new AbortController();
  // A timeout is a ceiling for a hung connection, not a substitute for the
  // server's own limits. 20s is comfortably above the slowest composed response.
  const timer = window.setTimeout(() => controller.abort(), timeout);

  const headers = { Accept: 'application/json' };
  const mutating = method !== 'GET' && method !== 'HEAD';
  if (mutating) {
    headers['Content-Type'] = 'application/json';
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
    if (idempotencyKey) headers[IDEMPOTENCY_HEADER] = idempotencyKey;
  }

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'same-origin',
      signal: controller.signal,
      cache: 'no-store',
    });
  } catch (error) {
    window.clearTimeout(timer);
    if (key) inflight.delete(key);
    if (error && error.name === 'AbortError') throw new AbortedError();
    // A network-level failure is not a 500 — the request never reached the server.
    throw new ApiError({
      code: 'DB_UNAVAILABLE',
      message: 'Нет связи с сервером.',
      status: 0,
    });
  }

  window.clearTimeout(timer);
  if (key) inflight.delete(key);

  let payload = null;
  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    try {
      payload = await response.json();
    } catch {
      // A 200 whose body is not valid JSON is a malformed response, and it must
      // be distinguishable from a 500 — the field that failed matters.
      throw new ApiError({
        code: 'VALIDATION_FAILED',
        message: 'Сервер вернул некорректный ответ.',
        status: response.status,
      });
    }
  }

  if (!response.ok) {
    const error = (payload && payload.error) || {};
    throw new ApiError({ ...error, status: response.status });
  }

  if (!payload || typeof payload !== 'object' || !('data' in payload)) {
    throw new ApiError({
      code: 'VALIDATION_FAILED',
      message: 'Ответ не соответствует контракту.',
      status: response.status,
    });
  }

  return { data: payload.data, meta: payload.meta || {}, replayed: response.headers.get('X-Idempotent-Replay') === '1' };
}

function withQuery(path, params) {
  if (!params) return path;
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue;
    search.set(name, String(value));
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function get(path, { params, key, timeout } = {}) {
  return request('GET', withQuery(path, params), { key, timeout });
}

export function post(path, body, { key, timeout, idempotencyKey } = {}) {
  return request('POST', path, { body, key, timeout, idempotencyKey });
}

/**
 * An idempotency key for a trading-capable action.
 *
 * `crypto.randomUUID` where available. The key is generated once per *user
 * intent* — the dialog mints it on open, not the fetch on send — so a double
 * click or a retry after a timeout carries the same key and cannot double-fire.
 */
export function newIdempotencyKey(action) {
  const random = window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.floor(Math.random() * 1e9).toString(36)}`;
  return `${action}:${random}`.slice(0, 80);
}

// ── Endpoints ────────────────────────────────────────────────────────────────
// Named so a path appears exactly once in the client and a rename is one edit.

export const api = {
  session: () => get('/api/v2/auth/session', { key: 'session' }),
  login: (username, password) => post('/api/v2/auth/login', { username, password }),
  logout: () => post('/api/v2/auth/logout', {}),
  changePassword: (currentPassword, newPassword) =>
    post('/api/v2/auth/password', { current_password: currentPassword, new_password: newPassword }),

  overview: (params) => get('/api/v2/overview', { params, key: 'overview' }),
  environment: (params) => get('/api/v2/environment', { params, key: 'environment' }),
  faults: (params) => get('/api/v2/faults', { params, key: 'faults' }),
  health: (params) => get('/api/v2/health', { params, key: 'health' }),

  equity: (params) => get('/api/v2/equity', { params, key: 'equity' }),
  underwater: (params) => get('/api/v2/equity/underwater', { params, key: 'underwater' }),
  drawdown: (params) => get('/api/v2/drawdown', { params, key: 'drawdown' }),
  accounts: (params) => get('/api/v2/accounts', { params, key: 'accounts' }),
  portfolio: (params) => get('/api/v2/portfolio', { params, key: 'portfolio' }),
  positions: (params) => get('/api/v2/positions', { params, key: 'positions' }),

  trades: (params) => get('/api/v2/trades', { params, key: 'trades' }),
  statistics: (params) => get('/api/v2/statistics', { params, key: 'statistics' }),
  distribution: (params) => get('/api/v2/statistics/distribution', { params, key: 'distribution' }),
  dailyPnl: (params) => get('/api/v2/analytics/daily', { params, key: 'dailyPnl' }),

  signals: (params) => get('/api/v2/signals', { params, key: 'signals' }),
  strategies: (params) => get('/api/v2/strategies', { params, key: 'strategies' }),
  strategyDetail: (id) => get(`/api/v2/strategies/${encodeURIComponent(id)}`, { key: `strategy:${id}` }),
  decisions: (params) => get('/api/v2/strategies/decisions', { params, key: 'decisions' }),
  hypotheses: (params) => get('/api/v2/hypotheses', { params, key: 'hypotheses' }),

  risk: (params) => get('/api/v2/risk', { params, key: 'risk' }),
  riskEvents: (params) => get('/api/v2/risk/events', { params, key: 'riskEvents' }),
  events: (params) => get('/api/v2/events', { params, key: 'events' }),
  audit: (params) => get('/api/v2/audit', { params, key: 'audit' }),
  marketCoverage: (params) => get('/api/v2/market/coverage', { params, key: 'marketCoverage' }),
  credentials: () => get('/api/v2/settings/credentials', { key: 'credentials' }),

  engineStart: (reason) => post('/api/v2/engine/start', { reason }),
  engineStop: (reason) => post('/api/v2/engine/stop', { reason }),
  acknowledgeFault: (code) => post(`/api/v2/faults/${encodeURIComponent(code)}/acknowledge`, {}),
  runLearningCycle: () => post('/api/v2/learning/run-cycle', {}),
  runBacktest: (body) => post('/api/v2/backtest/run', body, { timeout: 120000 }),

  closePosition: (id, { reason, confirm, idempotencyKey }) =>
    post(`/api/v2/positions/${id}/close`, { reason, confirm }, { idempotencyKey }),
  executeSignal: (id, { reason, idempotencyKey }) =>
    post(`/api/v2/signals/${id}/execute`, { reason }, { idempotencyKey }),

  saveCredential: (key, value, reason) =>
    post('/api/v2/settings/credentials', { key, value, reason }),
  clearCredential: (key, reason) =>
    post(`/api/v2/settings/credentials/${encodeURIComponent(key)}/clear`, { confirm: key, reason }),
  pruneEquity: (body) => post('/api/v2/maintenance/prune-equity', body),
};
