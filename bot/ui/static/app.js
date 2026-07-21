/* QuantFlow Application Core */

const PAGE_TITLES = {
  dashboard: ['Dashboard', 'Overview · Live'],
  portfolio: ['Portfolio', 'Assets · Allocation'],
  signals: ['Signals', 'Center · Live'],
  backtest: ['Backtest', 'Simulation · Analytics'],
  analytics: ['Analytics', 'Performance · Risk · History'],
  learning: ['Learning', 'Autonomous · AI · Sandbox'],
  settings: ['Settings', 'Configuration'],
  miniapp: ['Quant Hunter', 'Cryptonite · Mini App'],
};

const KEY_VIEWS = {
  '1': 'dashboard', '2': 'portfolio', '3': 'signals',
  '4': 'backtest',  '5': 'miniapp',  '6': 'analytics',
  '7': 'learning',  '8': 'settings',
};
const TICKER_COLORS = { SBER: '#F7931A', GAZP: '#3861fb', LKOH: '#00c076', NVTK: '#f6465d', YNDX: '#8b5cf6' };

const fmt = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtInt = new Intl.NumberFormat('ru-RU');

const _ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => _ESC_MAP[c]); }

function money(v) { return fmt.format(v) + ' ₽'; }
function pct(v) { return QFFmt.pct(v); }
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
  document.querySelectorAll('.sidebar-nav a[data-view], .nav a[data-view]').forEach(a => {
    const isActive = a.dataset.view === name;
    a.classList.toggle('active', isActive);
    if (isActive) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
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
    <tr><td class="ts-cell">${esc(r.ts)}</td><td class="ticker-cell">${esc(r.ticker)}</td>
    <td>${badgeHTML(r.action)}</td><td class="price-cell num">${fmt.format(r.price)}</td>
    <td class="num">${fmt.format(r.score)}</td></tr>`).join('');
  const su = document.getElementById('signalsUpdated');
  if (su) su.textContent = new Date().toLocaleTimeString('ru-RU', { hour12: false });
}

async function loadLog() {
  const data = await fetchJSON('/api/log').catch(() => []);
  const list = document.getElementById('logList');
  if (!list) return;
  if (!data.length) { list.innerHTML = '<div class="empty">Лог пуст</div>'; return; }
  list.innerHTML = data.map(e => `
    <div class="log-entry"><span class="log-ts">${esc(e.ts)}</span>${logBadge(e.level)}<span class="log-msg">${esc(e.message)}</span></div>`).join('');
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
      const eticker = esc(t.ticker);
      return `<div class="ticker-card" data-ticker="${eticker}">
        <div class="ticker-card-symbol" style="color:${color}">${eticker}</div>
        <div class="ticker-card-price">${fmt.format(t.price)} ₽</div>
        <div class="ticker-card-change ${cls}">${pct(t.change_1d)}</div></div>`;
    }).join('');
    if (grid) grid.querySelectorAll('.ticker-card[data-ticker]').forEach(el =>
      el.addEventListener('click', () => loadTickerChart(el.dataset.ticker))
    );
    if (tabs) tabs.innerHTML = data.map(t =>
      `<button type="button" class="ticker-tab" data-ticker="${esc(t.ticker)}">${esc(t.ticker)}</button>`
    ).join('');
    if (tabs) tabs.querySelectorAll('.ticker-tab[data-ticker]').forEach(el =>
      el.addEventListener('click', () => loadTickerChart(el.dataset.ticker))
    );
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
    if (eye) eye.classList.toggle('active', visible);
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
initCredentialField('inputBybitApiKey', 'eyeBybitApiKey', 'saveBybitApiKey', 'clearBybitApiKey', 'statusBybitApiKey', 'BYBIT_API_KEY');
initCredentialField('inputBybitApiSecret', 'eyeBybitApiSecret', 'saveBybitApiSecret', 'clearBybitApiSecret', 'statusBybitApiSecret', 'BYBIT_API_SECRET');

// Broker tab switching
(function initBrokerTabs() {
  const tabs = document.querySelectorAll('.broker-tab[data-broker]');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const broker = tab.dataset.broker;
      tabs.forEach(t => t.classList.toggle('active', t === tab));
      document.querySelectorAll('.broker-panel').forEach(p => {
        p.style.display = p.id === `brokerPanel-${broker}` ? '' : 'none';
      });
    });
  });
})();

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
    if (eye) eye.classList.toggle('active', visible);
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
    const pairs = [
      ['statusTinkoffToken', d.has_tinkoff_token],
      ['statusTinkoffAccountId', d.has_tinkoff_account_id],
    ];
    pairs.forEach(([id, ok]) => {
      const el = document.getElementById(id);
      if (el && !el.textContent) {
        el.textContent = ok ? '● Configured' : '○ Not set';
        el.className = 'credential-status ' + (ok ? 'cred-set' : 'cred-err');
      }
    });
    // Update broker status dots
    const tinkoffOk = d.has_tinkoff_token && d.has_tinkoff_account_id;
    const dot = document.getElementById('brokerDotTinkoff');
    if (dot) dot.className = 'broker-tab-dot ' + (tinkoffOk ? 'online' : 'offline');
    const bybitDot = document.getElementById('brokerDotBybit');
    if (bybitDot) bybitDot.className = 'broker-tab-dot'; // will check bybit separately when API supports it
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
    if (grid) grid.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  } finally {
    await loadTokenStatus();
  }
}

viewHandlers.settings = loadSettings;

/* ── Analytics ── */
async function loadAnalytics() {
  try {
    // Engine status
    const status = await QFApi.engineStatus().catch(() => ({ running: false }));
    const btn = document.getElementById('engineStartBtn');
    const statusTxt = document.getElementById('engineStatusText');
    if (statusTxt) {
      statusTxt.textContent = status.running ? '🟢 Запущен' : '🔴 Остановлен';
      statusTxt.className = 'as-val ' + (status.running ? 'positive' : 'negative');
    }
    if (btn) {
      btn.textContent = status.running ? '⏹ Остановить' : '▶ Запустить';
      btn.onclick = async () => {
        if (status.running) await QFApi.engineStop(); else await QFApi.engineStart();
        loadAnalytics();
      };
    }

    // Analytics data
    const data = await QFApi.analytics().catch(() => null);
    if (!data) return;

    const { stats, equity_curve, monthly_pnl, daily_pnl, best_worst } = data;

    // Stats grid
    if (stats) {
      const set = (id, val, cls) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = val;
        if (cls) {
          // preserve base class (qf-strip-value, metric-value, etc.), swap only color
          const base = (el.className || 'metric-value').replace(/\b(positive|negative|neutral)\b/g, '').trim() || 'metric-value';
          el.className = base + ' ' + cls;
        }
      };
      const colorClass = (v) => v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral';
      set('anTotalTrades', stats.total_trades ?? '—');
      set('anWinRate', stats.win_rate != null ? stats.win_rate.toFixed(1) + '%' : '—', colorClass(stats.win_rate - 50));
      set('anProfitFactor', stats.profit_factor != null ? stats.profit_factor.toFixed(2) : '—', colorClass(stats.profit_factor - 1));
      set('anSharpe', stats.sharpe_ratio != null ? stats.sharpe_ratio.toFixed(2) : '—', colorClass(stats.sharpe_ratio));
      set('anSortino', stats.sortino_ratio != null ? stats.sortino_ratio.toFixed(2) : '—', colorClass(stats.sortino_ratio));
      set('anMaxDD', stats.max_drawdown != null ? '-' + stats.max_drawdown.toFixed(1) + '%' : '—', 'negative');
      set('anTotalPnl', stats.total_pnl != null ? (stats.total_pnl >= 0 ? '+' : '') + fmt.format(stats.total_pnl) + ' ₽' : '—', colorClass(stats.total_pnl));
      set('anRoi', stats.roi_pct != null ? (stats.roi_pct >= 0 ? '+' : '') + stats.roi_pct.toFixed(2) + '%' : '—', colorClass(stats.roi_pct));
    }

    // Equity curve
    if (equity_curve?.length) {
      QFChart.line('analyticsEquityChart', equity_curve.map(p => ({ time: p.ts, value: p.equity })));
      const first = equity_curve[0]?.equity || 0, last = equity_curve[equity_curve.length - 1]?.equity || 0;
      const diff = last - first;
      const sub = document.getElementById('equitySubtitle');
      if (sub) {
        sub.textContent = `${equity_curve.length} точек · ${diff >= 0 ? '+' : ''}${fmt.format(diff)} ₽`;
        sub.className = 'card-subtitle ' + (diff >= 0 ? 'sub-positive' : 'sub-negative');
      }
    }

    // Monthly P&L — bar chart for ≥2 months, stat tile for single month
    const monthlyEl = document.getElementById('analyticsMonthlyChart');
    if (monthlyEl && monthly_pnl?.length) {
      if (monthly_pnl.length >= 2 && typeof echarts !== 'undefined') {
        const existing = echarts.getInstanceByDom(monthlyEl);
        if (existing) existing.dispose();
        const chart = echarts.init(monthlyEl, 'dark');
        chart.setOption({
          backgroundColor: 'transparent',
          grid: { top: 20, right: 10, bottom: 30, left: 60 },
          xAxis: { type: 'category', data: monthly_pnl.map(m => m.month), axisLabel: { color: '#848e9c', fontSize: 11 } },
          yAxis: { type: 'value', axisLabel: { color: '#848e9c', fontSize: 11, formatter: v => (v >= 0 ? '' : '-') + Math.abs(v/1000).toFixed(0) + 'K' } },
          series: [{
            type: 'bar', data: monthly_pnl.map(m => ({
              value: m.pnl,
              itemStyle: { color: m.pnl >= 0 ? '#00c076' : '#f6465d', borderRadius: [3, 3, 0, 0] }
            })),
            barMaxWidth: 40,
          }],
          tooltip: { trigger: 'axis', backgroundColor: '#161a22', borderColor: '#2a2e38', textStyle: { color: '#eaecef' }, formatter: p => `${p[0].name}<br/>${p[0].value >= 0 ? '+' : ''}${fmt.format(p[0].value)} ₽` }
        });
      } else {
        // Single month — show as readable stat
        const m = monthly_pnl[0];
        const cls = (m.pnl || 0) >= 0 ? 'positive' : 'negative';
        const sign = (m.pnl || 0) >= 0 ? '+' : '';
        monthlyEl.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;gap:8px;padding:20px">
          <div style="font-size:11px;color:var(--qf-text-muted);text-transform:uppercase;letter-spacing:.06em">${m.month || 'Current Month'}</div>
          <div style="font-family:var(--qf-font-mono);font-size:28px;font-weight:700;letter-spacing:-.02em" class="${cls}">${sign}${fmt.format(m.pnl || 0)} ₽</div>
          <div style="font-size:11px;color:var(--qf-text-muted)">${m.trades || 0} сделок</div>
        </div>`;
      }
    }

    // Daily PnL table
    const dailyBody = document.getElementById('analyticsDailyBody');
    if (dailyBody) {
      dailyBody.innerHTML = (daily_pnl || []).length
        ? [...(daily_pnl || [])].reverse().map(d => {
            const cls = d.pnl >= 0 ? 'positive' : 'negative';
            return `<tr><td class="ts-cell">${d.day}</td><td class="${cls}">${d.pnl >= 0 ? '+' : ''}${fmt.format(d.pnl)} ₽</td><td>${d.trades}</td></tr>`;
          }).join('')
        : '<tr><td colspan="3" class="empty">Нет данных</td></tr>';
    }

    // Best/worst trades — labels adapt to whether all trades are losses
    const renderTrades = (id, trades) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = (trades || []).map(t => {
        const pnl = t.pnl || 0;
        const cls = pnl >= 0 ? 'positive' : 'negative';
        return `<div class="recent-item">
          <span class="recent-ticker">${esc(t.ticker)}</span>
          <span class="${cls}">${pnl >= 0 ? '+' : ''}${fmt.format(pnl)} ₽</span>
        </div>`;
      }).join('') || '<div class="empty">—</div>';
    };
    const bestTrades = best_worst?.best || [];
    const worstTrades = best_worst?.worst || [];
    // Relabel "Best" when all are negative (no profitable trades)
    const allBestNegative = bestTrades.length > 0 && bestTrades.every(t => (t.pnl || 0) < 0);
    const bestHeader = document.querySelector('#analyticsBestTrades')?.closest('.card')?.querySelector('.card-title');
    if (bestHeader && allBestNegative) bestHeader.textContent = 'Наименьшие убытки';
    else if (bestHeader) bestHeader.textContent = 'Лучшие сделки';
    renderTrades('analyticsBestTrades', bestTrades);
    renderTrades('analyticsWorstTrades', worstTrades);

    // Closed trades history table
    const tradesData = await QFApi.paperTrades(30).catch(() => ({ trades: [] }));
    const tradesBody = document.getElementById('tradesHistoryBody');
    const tradesMeta = document.getElementById('tradesHistoryMeta');
    if (tradesBody) {
      const trades = tradesData.trades || [];
      if (tradesMeta) tradesMeta.textContent = `${trades.length} сделок`;
      tradesBody.innerHTML = trades.map(t => {
        const cls = (t.pnl || 0) >= 0 ? 'positive' : 'negative';
        const reasonBadge = { SL_HIT: 'badge-error', TP_HIT: 'badge-buy', manual: 'badge-hold', SIGNAL: 'badge-info' }[t.close_reason] || 'badge-hold';
        return `<tr>
          <td class="ticker-cell">${t.ticker}</td>
          <td>${QFUI.badge(t.direction)}</td>
          <td class="price-cell num">${fmt.format(t.entry_price)}</td>
          <td class="price-cell num">${fmt.format(t.exit_price)}</td>
          <td class="num">${t.quantity}</td>
          <td class="num ${cls}">${(t.pnl||0) >= 0 ? '+' : ''}${fmt.format(t.pnl||0)} ₽</td>
          <td class="num ${cls}">${((t.pnl_pct||0)*100).toFixed(2)}%</td>
          <td class="price-cell num">${fmt.format(t.commission||0)} ₽</td>
          <td><span class="badge ${reasonBadge}">${t.close_reason || 'manual'}</span></td>
          <td class="ts-cell">${(t.closed_at || '').slice(0, 16)}</td>
        </tr>`;
      }).join('') || '<tr><td colspan="10" class="empty">Нет сделок</td></tr>';
    }

  } catch (err) {
    console.warn('[Analytics]', err);
  }
}

viewHandlers.analytics = loadAnalytics;

document.getElementById('refreshAnalyticsBtn')?.addEventListener('click', loadAnalytics);

window.showView = showView;
window.loadTickerChart = loadTickerChart;
window.dashboardRefresh = dashboardRefresh;
window.dashboardRefreshCore = dashboardRefreshCore;
window.fetchJSON = fetchJSON;
window.dashboardApiHeaders = dashboardApiHeaders;
window.setRiskBar = setRiskBar;

/* ── Paper Trading Live Feed ── */
(function initPaperFeed() {
  const MAX_ITEMS = 30;

  function renderFeedItem(data) {
    const feed = document.getElementById('paperFeedList');
    if (!feed) return;
    const empty = feed.querySelector('.empty');
    if (empty) empty.remove();

    const status = document.getElementById('paperFeedStatus');
    if (status) { status.textContent = 'Live'; status.className = 'badge badge-buy'; }

    const action = (data.action || 'OPEN').toUpperCase();
    const ticker = data.ticker || '—';
    const price = data.entry_price ? fmt.format(data.entry_price) : '—';
    const prob = data.probability_pct ? ` · ${data.probability_pct}%` : '';
    const cls = ['BUY', 'LONG', 'OPEN'].includes(action) ? 'badge-buy' : 'badge-sell';
    const ts = new Date().toLocaleTimeString('ru-RU', { hour12: false });

    const item = document.createElement('div');
    item.className = 'paper-feed-item';
    item.innerHTML = `<span class="badge ${cls}">${esc(action)}</span><span class="feed-ticker">${esc(ticker)}</span><span class="feed-price">${esc(price)}${esc(prob)}</span><span class="feed-ts">${esc(ts)}</span>`;

    feed.insertBefore(item, feed.firstChild);
    while (feed.children.length > MAX_ITEMS) feed.removeChild(feed.lastChild);
  }

  function renderCloseFeedItem(data) {
    const feed = document.getElementById('paperFeedList');
    if (!feed) return;
    const empty = feed.querySelector('.empty');
    if (empty) empty.remove();

    const status = document.getElementById('paperFeedStatus');
    if (status) { status.textContent = 'Live'; status.className = 'badge badge-buy'; }

    const ticker = data.ticker || '—';
    const pnl = data.pnl != null ? (data.pnl >= 0 ? '+' : '') + fmt.format(data.pnl) : '—';
    const reason = data.reason || 'close';
    const cls = (data.pnl >= 0) ? 'badge-buy' : 'badge-sell';
    const ts = new Date().toLocaleTimeString('ru-RU', { hour12: false });

    const item = document.createElement('div');
    item.className = 'paper-feed-item';
    item.innerHTML = `<span class="badge ${cls}">CLOSE</span><span class="feed-ticker">${esc(ticker)}</span><span class="feed-price">P&amp;L ${esc(pnl)}</span><span class="feed-ts">${esc(ts)} · ${esc(reason)}</span>`;

    feed.insertBefore(item, feed.firstChild);
    while (feed.children.length > MAX_ITEMS) feed.removeChild(feed.lastChild);
  }

  if (typeof QFStore !== 'undefined') {
    QFStore.on?.('event:paper_trade_executed', (payload) => {
      const raw = payload?.raw || payload || {};
      renderFeedItem(raw?.data || raw);
    });
    QFStore.on?.('event:paper_position_closed', (payload) => {
      const raw = payload?.raw || payload || {};
      renderCloseFeedItem(raw?.data || raw);
    });
    QFStore.on?.('sync:complete', () => {
      const state = QFStore.get();
      const positions = state.paperPositions || [];
      if (positions.length) {
        const status = document.getElementById('paperFeedStatus');
        if (status && status.textContent === 'Ожидание…') {
          status.textContent = `${positions.length} позиций`;
          status.className = 'badge badge-buy';
        }
      }
    });
  }

  document.addEventListener('sseEvent', (e) => {
    if (e.detail?.type === 'paper_trade_executed') renderFeedItem(e.detail.data || {});
    if (e.detail?.type === 'paper_position_closed') renderCloseFeedItem(e.detail.data || {});
  });
})();