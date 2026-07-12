/* QuantFlow Application Core */

const PAGE_TITLES = {
  dashboard: ['Dashboard', 'Overview · Live'],
  portfolio: ['Portfolio', 'Assets · Allocation'],
  signals: ['Signals', 'Center · Live'],
  backtest: ['Backtest', 'Simulation · Analytics'],
  settings: ['Settings', 'Configuration'],
  miniapp: ['Quant Hunter', 'Cryptonite · Mini App'],
};

const KEY_VIEWS = { '1': 'dashboard', '2': 'portfolio', '3': 'signals', '4': 'backtest', '5': 'miniapp' };
const TICKER_COLORS = { SBER: '#00c076', GAZP: '#3861fb', LKOH: '#f0b90b', NVTK: '#f6465d', YNDX: '#8b5cf6' };

const fmt = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtInt = new Intl.NumberFormat('ru-RU');

function money(v) { return fmt.format(v) + ' ₽'; }
function pct(v) { return (v >= 0 ? '+' : '') + fmt.format(v) + '%'; }
function colorClass(v) { return v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral'; }

function applyColor(el, v) {
  if (!el) return;
  el.classList.remove('positive', 'negative', 'neutral');
  el.classList.add(colorClass(v));
}

function badgeHTML(action) { return QFUI.badge(action); }

function logBadge(level) {
  const l = (level || '').toUpperCase();
  if (l === 'ERROR') return '<span class="badge badge-error">ERR</span>';
  if (l === 'WARN' || l === 'WARNING') return '<span class="badge badge-warn">WARN</span>';
  return '<span class="badge badge-info">INFO</span>';
}

function animateValue(el, targetVal, formatter, duration = 650) {
  if (!el) return;
  const startVal = parseFloat(el.dataset.rawVal) || 0;
  if (Math.abs(targetVal - startVal) < 0.005) {
    el.textContent = formatter(targetVal);
    el.dataset.rawVal = targetVal;
    return;
  }
  el.dataset.rawVal = targetVal;
  if (el._raf) cancelAnimationFrame(el._raf);
  const t0 = performance.now();
  function step(now) {
    const t = Math.min((now - t0) / duration, 1);
    const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    el.textContent = formatter(startVal + (targetVal - startVal) * e);
    el._raf = t < 1 ? requestAnimationFrame(step) : null;
  }
  el._raf = requestAnimationFrame(step);
}

const _controllers = new Map();

function dashboardApiHeaders(extra = {}) {
  const headers = { ...extra };
  const apiKey = sessionStorage.getItem('dashboard_api_key');
  if (apiKey) headers['X-Dashboard-Api-Key'] = apiKey;
  return headers;
}

async function fetchJSON(url, opts = {}) {
  opts.headers = dashboardApiHeaders(opts.headers || {});
  if (!opts.method || opts.method === 'GET') {
    _controllers.get(url)?.abort();
    const ctrl = new AbortController();
    _controllers.set(url, ctrl);
    const tid = setTimeout(() => ctrl.abort(), 10000);
    try {
      const res = await fetch(url, { ...opts, signal: ctrl.signal });
      clearTimeout(tid);
      _controllers.delete(url);
      if (!res.ok) {
        let b = {};
        try { b = await res.json(); } catch (_) {}
        const err = new Error(b.error || `HTTP ${res.status}`);
        err.errorCode = b.error_code || 'HTTP_ERROR';
        err.status = res.status;
        throw err;
      }
      return res.json();
    } catch (e) {
      clearTimeout(tid);
      _controllers.delete(url);
      if (e.name === 'AbortError') {
        const err = new Error('Таймаут соединения');
        err.errorCode = 'TIMEOUT';
        throw err;
      }
      throw e;
    }
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let b = {};
    try { b = await res.json(); } catch (_) {}
    const err = new Error(b.error || `HTTP ${res.status}`);
    err.errorCode = b.error_code || 'HTTP_ERROR';
    throw err;
  }
  return res.json();
}

/* ── Navigation ── */
const viewHandlers = {};
let currentView = 'dashboard';

function showView(name) {
  const prev = currentView;
  if (prev === 'miniapp' && name !== 'miniapp') {
    window.MiniAppBridge?.destroy?.();
  }

  document.querySelectorAll('.view').forEach(v =>
    v.classList.toggle('active', v.id === `view-${name}`)
  );
  document.querySelectorAll('.sidebar-nav a[data-view], .nav a[data-view]').forEach(a =>
    a.classList.toggle('active', a.dataset.view === name)
  );
  currentView = name;

  if (name === 'miniapp') {
    window.AppLayout?.enterMiniApp?.();
  } else {
    window.AppLayout?.enterDashboard?.();
    window.SidebarProvider?.closeMobile?.();
  }

  const [title, crumb] = PAGE_TITLES[name] || [name, ''];
  const pageTitle = document.getElementById('pageTitle');
  const pageBreadcrumb = document.getElementById('pageBreadcrumb');
  if (pageTitle) pageTitle.textContent = title;
  if (pageBreadcrumb) pageBreadcrumb.textContent = crumb;

  viewHandlers[name]?.();

  if (name !== 'miniapp') {
    requestAnimationFrame(() => QFChart?.resizeAll());
  }
}

document.querySelectorAll('.sidebar-nav a[data-view]').forEach(a => {
  a.addEventListener('click', e => { e.preventDefault(); showView(a.dataset.view); });
});

window.SidebarProvider?.init?.();
window.SidebarProvider?.on?.(() => {
  if (currentView !== 'miniapp') requestAnimationFrame(() => QFChart?.resizeAll());
});

document.addEventListener('keydown', e => {
  if (e.target.matches('input, textarea, select, [contenteditable]')) return;
  if (KEY_VIEWS[e.key]) {
    e.preventDefault();
    showView(KEY_VIEWS[e.key]);
    return;
  }
  if (e.key === 'r' || e.key === 'R') {
    e.preventDefault();
    document.getElementById('topbarRefreshBtn')?.click();
  }
});

/* ── Clock ── */
function updateClock() {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleTimeString('ru-RU', { hour12: false }) + ' MSK';
}
updateClock();
setInterval(updateClock, 1000);

function setBotStatus(state) {
  const sb = document.getElementById('botStatus');
  const txt = document.getElementById('botStatusText');
  if (!sb) return;
  sb.className = 'status-badge ' + state;
  txt.textContent = state === 'live' ? 'Connected' : state === 'stopped' ? 'Offline' : 'Connecting';
}

function setRiskBar(barId, valId, pctVal, label, warnAt, dangerAt) {
  const bar = document.getElementById(barId);
  if (!bar) return;
  bar.style.width = Math.min(Math.max(pctVal, 0), 100) + '%';
  bar.className = 'risk-bar-fill';
  if (dangerAt > 0 && pctVal >= dangerAt) bar.classList.add('danger');
  else if (warnAt > 0 && pctVal >= warnAt) bar.classList.add('warn');
  const vel = document.getElementById(valId);
  if (vel) vel.textContent = label;
}

/* ── Dashboard loaders (legacy / supplemental) ── */
async function loadBotStats() {
  const ddEl = document.getElementById('metDrawdown');
  const wrEl = document.getElementById('metWinRate');
  const shEl = document.getElementById('metSharpe');
  try {
    const d = await fetchJSON('/api/stats');
    if (d.max_drawdown != null && ddEl) {
      ddEl.textContent = pct(-Math.abs(d.max_drawdown));
      applyColor(ddEl, -Math.abs(d.max_drawdown));
    }
    if (d.win_rate != null && wrEl) wrEl.textContent = 'Win rate ' + fmt.format(d.win_rate) + '%';
    if (d.sharpe_ratio != null && shEl) {
      shEl.textContent = fmt.format(d.sharpe_ratio);
      shEl.className = 'metric-value ' + colorClass(d.sharpe_ratio);
    }
    return d;
  } catch (_) {
    [ddEl, shEl].forEach(el => { if (el) { el.textContent = '—'; el.className = 'metric-value neutral'; } });
    if (wrEl) wrEl.textContent = 'Нет данных';
    return null;
  }
}

async function loadEquity() {
  const sub = document.getElementById('chartSubtitle');
  try {
    const data = await fetchJSON('/api/equity');
    if (!data.length) {
      if (sub) sub.textContent = 'Нет данных о закрытых сделках';
      QFChart.showEmpty('equityChart');
      return;
    }
    QFChart.line('equityChart', data.map(d => ({ time: d.ts, value: d.equity })));
    const first = data[0]?.equity || 0;
    const last = data[data.length - 1]?.equity || 0;
    const diff = last - first;
    const diffP = first ? diff / first * 100 : 0;
    if (sub) {
      sub.textContent = `${data.length} точек · ${diff >= 0 ? '+' : ''}${fmt.format(diff)} ₽ (${pct(diffP)})`;
      sub.className = 'card-subtitle ' + (diff >= 0 ? 'sub-positive' : 'sub-negative');
    }
  } catch (_) {
    if (sub) sub.textContent = 'Нет данных об истории';
    QFChart.showEmpty('equityChart');
  }
}

async function loadSignals() {
  const data = await fetchJSON('/api/signals').catch(() => []);
  const tbody = document.getElementById('signalsBody');
  if (!tbody) return;
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">Нет сигналов</td></tr>';
    return;
  }
  tbody.innerHTML = data.slice(0, 20).map(r => `
    <tr><td class="ts-cell">${r.ts}</td><td class="ticker-cell">${r.ticker}</td>
    <td>${badgeHTML(r.action)}</td><td class="price-cell">${fmt.format(r.price)}</td>
    <td>${fmt.format(r.score)}</td></tr>`).join('');
  const su = document.getElementById('signalsUpdated');
  if (su) su.textContent = new Date().toLocaleTimeString('ru-RU', { hour12: false });
}

async function loadLog() {
  const data = await fetchJSON('/api/log').catch(() => []);
  const list = document.getElementById('logList');
  if (!list) return;
  if (!data.length) { list.innerHTML = '<div class="empty">Лог пуст</div>'; return; }
  list.innerHTML = data.map(e => `
    <div class="log-entry"><span class="log-ts">${e.ts}</span>${logBadge(e.level)}<span class="log-msg">${e.message}</span></div>`).join('');
}

async function dashboardRefreshCore() {
  if (typeof QFSync !== 'undefined') return QFSync.fullSync(true);
  await Promise.allSettled([loadBotStats(), loadEquity(), loadLog()]);
}

async function dashboardRefresh() {
  if (typeof refreshDashboard === 'function') return refreshDashboard();
  if (currentView !== 'dashboard') return;
  await dashboardRefreshCore();
}

document.getElementById('topbarRefreshBtn')?.addEventListener('click', () => {
  if (currentView === 'dashboard') dashboardRefresh();
  else viewHandlers[currentView]?.();
});

/* ── Portfolio market data ── */
async function loadTickerChart(ticker) {
  document.getElementById('portfolioChartTitle').textContent = `${ticker} — Дневные свечи`;
  document.getElementById('portfolioChartSub').textContent = 'Загрузка…';
  document.querySelectorAll('.ticker-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.ticker === ticker)
  );
  try {
    const data = await fetchJSON(`/api/candles?ticker=${ticker}&limit=120`);
    if (!data.length) {
      document.getElementById('portfolioChartSub').textContent = 'Нет данных';
      QFChart.showEmpty('portfolioChart');
      return;
    }
    QFChart.candles('portfolioChart', data);
    const first = data[0]?.close || 0;
    const last = data[data.length - 1]?.close || 0;
    const diff = last - first;
    const diffP = first ? diff / first * 100 : 0;
    const sub = document.getElementById('portfolioChartSub');
    sub.textContent = `${data.length} дней · ${diff >= 0 ? '+' : ''}${fmt.format(diff)} ₽ (${pct(diffP)})`;
    sub.className = 'card-subtitle ' + (diff >= 0 ? 'sub-positive' : 'sub-negative');
  } catch (_) {
    document.getElementById('portfolioChartSub').textContent = 'Нет данных';
    QFChart.showEmpty('portfolioChart');
  }
}

async function loadPortfolio() {
  const grid = document.getElementById('tickerGrid');
  const tabs = document.getElementById('tickerTabs');
  try {
    const data = await fetchJSON('/api/portfolio');
    if (!data.length) {
      if (grid) grid.innerHTML = '<div class="empty">Нет котировок</div>';
      return;
    }
    if (grid) grid.innerHTML = data.map(t => {
      const cls = t.change_1d >= 0 ? 'positive' : 'negative';
      const color = TICKER_COLORS[t.ticker] || '#848e9c';
      return `<div class="ticker-card" onclick="loadTickerChart('${t.ticker}')">
        <div class="ticker-card-symbol" style="color:${color}">${t.ticker}</div>
        <div class="ticker-card-price">${fmt.format(t.price)} ₽</div>
        <div class="ticker-card-change ${cls}">${pct(t.change_1d)}</div></div>`;
    }).join('');
    if (tabs) tabs.innerHTML = data.map(t =>
      `<button type="button" class="ticker-tab" data-ticker="${t.ticker}" onclick="loadTickerChart('${t.ticker}')">${t.ticker}</button>`
    ).join('');
    if (data.length) loadTickerChart(data[0].ticker);
  } catch (_) {
    if (grid) grid.innerHTML = '<div class="empty">Ошибка загрузки</div>';
  }
}

viewHandlers.portfolio = loadPortfolio;

/* ── Settings ── */
function initCredentialField(inputId, eyeId, saveId, clearId, statusId, envKey) {
  const input = document.getElementById(inputId);
  const eye = document.getElementById(eyeId);
  const save = document.getElementById(saveId);
  const clear = document.getElementById(clearId);
  const status = document.getElementById(statusId);
  if (!input) return;
  let visible = false;
  eye?.addEventListener('click', () => {
    visible = !visible;
    input.type = visible ? 'text' : 'password';
    if (eye) eye.textContent = visible ? '🙈' : '👁';
  });
  async function persist(value) {
    if (save) save.disabled = true;
    if (status) { status.textContent = 'Сохранение…'; status.className = 'credential-status'; }
    try {
      const res = await fetch('/api/settings/tokens', {
        method: 'POST',
        headers: dashboardApiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ key: envKey, value }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Ошибка');
      if (status) { status.textContent = '✓ Сохранено'; status.className = 'credential-status cred-ok'; }
      QFUI.toast('Учётные данные сохранены', 'success');
      if (currentView === 'dashboard' && typeof loadPlatformOverview === 'function') loadPlatformOverview();
    } catch (err) {
      if (status) { status.textContent = '✗ ' + err.message; status.className = 'credential-status cred-err'; }
      QFUI.toast(err.message, 'error');
    } finally {
      if (save) save.disabled = false;
      setTimeout(() => { if (status) status.textContent = ''; }, 4000);
    }
  }
  save?.addEventListener('click', () => persist(input.value));
  clear?.addEventListener('click', () => { input.value = ''; persist(''); });
}

initCredentialField('inputTinkoffToken', 'eyeTinkoffToken', 'saveTinkoffToken', 'clearTinkoffToken', 'statusTinkoffToken', 'TINKOFF_TOKEN');
initCredentialField('inputTinkoffAccountId', 'eyeTinkoffAccountId', 'saveTinkoffAccountId', 'clearTinkoffAccountId', 'statusTinkoffAccountId', 'TINKOFF_ACCOUNT_ID');

(function initDashboardApiKeyField() {
  const input = document.getElementById('inputDashboardApiKey');
  const save = document.getElementById('saveDashboardApiKey');
  const clear = document.getElementById('clearDashboardApiKey');
  const status = document.getElementById('statusDashboardApiKey');
  const eye = document.getElementById('eyeDashboardApiKey');
  if (!input) return;
  let visible = false;
  const stored = sessionStorage.getItem('dashboard_api_key');
  if (stored) input.value = stored;
  eye?.addEventListener('click', () => {
    visible = !visible;
    input.type = visible ? 'text' : 'password';
    eye.textContent = visible ? '🙈' : '👁';
  });
  save?.addEventListener('click', () => {
    sessionStorage.setItem('dashboard_api_key', input.value.trim());
    if (status) { status.textContent = '✓ Сохранён'; status.className = 'credential-status cred-ok'; }
    QFUI.toast('API-ключ сохранён в сессии', 'success');
  });
  clear?.addEventListener('click', () => {
    sessionStorage.removeItem('dashboard_api_key');
    input.value = '';
    if (status) { status.textContent = '✓ Удалён'; status.className = 'credential-status cred-ok'; }
    QFUI.toast('API-ключ удалён', 'info');
  });
})();

async function loadTokenStatus() {
  try {
    const d = await fetchJSON('/api/settings/tokens');
    ['statusTinkoffToken', 'statusTinkoffAccountId'].forEach((id, i) => {
      const el = document.getElementById(id);
      const ok = i === 0 ? d.has_tinkoff_token : d.has_tinkoff_account_id;
      if (el && !el.textContent) {
        el.textContent = ok ? '● Настроен' : '○ Не задан';
        el.className = 'credential-status ' + (ok ? 'cred-set' : 'cred-err');
      }
    });
  } catch (_) {}
}

async function loadSettings() {
  const grid = document.getElementById('settingsGrid');
  const infoRows = document.getElementById('tinkoffInfoRows');
  try {
    const d = await fetchJSON('/api/settings');
    const sec = (title, rows) => `
      <div class="card settings-section"><div class="card-header"><div class="card-title">${title}</div></div>
      <div class="settings-rows">${rows.map(([k, v, ok]) => `
        <div class="settings-row"><span class="settings-key">${k}</span>
        <span class="settings-val ${ok !== undefined ? (ok ? 'positive' : 'negative') : ''}">${v}</span></div>`).join('')}
      </div></div>`;
    if (grid) grid.innerHTML = [
      sec('База данных', [['Хост', d.db.host + ':' + d.db.port], ['База', d.db.name], ['Статус', d.db.connected ? 'Online' : 'Error', d.db.connected]]),
      sec('Риск', [['Макс. позиция', (d.risk.max_position_pct * 100).toFixed(1) + '%'], ['ATR ×', d.risk.atr_stop_multiplier], ['Макс. позиций', d.risk.max_open_positions]]),
      sec('Приложение', [['Тикеры', d.app.tickers.join(', ')], ['Poll', d.app.poll_interval + 's'], ['Logs', d.app.log_level]]),
    ].join('');
    const connected = d.tinkoff.has_token && d.tinkoff.has_account_id;
    if (infoRows) infoRows.innerHTML = [
      ['Режим', d.tinkoff.sandbox ? 'Sandbox' : 'Production'],
      ['Статус', connected ? 'Настроен' : 'Не настроен', connected],
    ].map(([k, v, ok]) => `<div class="settings-row"><span class="settings-key">${k}</span>
      <span class="settings-val ${ok !== undefined ? (ok ? 'positive' : 'negative') : ''}">${v}</span></div>`).join('');
    window._maxOpenPositions = d.risk.max_open_positions;
  } catch (err) {
    if (grid) grid.innerHTML = `<div class="empty">${err.message}</div>`;
  } finally {
    await loadTokenStatus();
  }
}

viewHandlers.settings = loadSettings;

window.showView = showView;
window.loadTickerChart = loadTickerChart;
window.dashboardRefresh = dashboardRefresh;
window.dashboardRefreshCore = dashboardRefreshCore;
window.fetchJSON = fetchJSON;
window.dashboardApiHeaders = dashboardApiHeaders;
window.setRiskBar = setRiskBar;