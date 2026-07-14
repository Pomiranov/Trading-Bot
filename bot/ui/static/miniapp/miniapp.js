/* QuantFlow Mini App shell */

(function () {
  const params = new URLSearchParams(location.search);
  const inDashboard = !!document.getElementById('view-miniapp');
  const embedded = params.get('embed') === '1' || inDashboard;
  if (embedded) {
    document.documentElement.classList.add('embedded');
    if (inDashboard) document.getElementById('view-miniapp')?.classList.add('ma-embed-active');
  }

  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
    if (tg.themeParams.bg_color) document.body.style.backgroundColor = tg.themeParams.bg_color;
    const user = tg.initDataUnsafe?.user;
    if (user) {
      const el = document.getElementById('maUser');
      if (el) el.textContent = user.first_name || user.username || 'Quant Hunter';
    }
  }

  function toast(msg, type = 'info') {
    const root = document.getElementById('maToast');
    if (!root) return;
    const el = document.createElement('div');
    el.className = `ma-toast ma-toast-${type === 'success' ? 'success' : type === 'warn' ? 'warn' : 'info'}`;
    el.textContent = msg;
    root.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 2800);
  }
  window.maToast = toast;

  let activeTab = inDashboard ? 'game' : (new URLSearchParams(location.search).get('tab') === 'trade' ? 'trade' : 'game');
  let started = false;
  let tabsWired = false;
  let syncIv = null;
  let sse = null;

  function wireTabs() {
    if (tabsWired) return;
    tabsWired = true;
    document.querySelectorAll('.ma-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const name = tab.dataset.tab;
        if (name === activeTab) return;
        if (activeTab === 'game') QuantHunter.destroy();
        activeTab = name;

        document.querySelectorAll('.ma-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.ma-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${name}`)?.classList.add('active');

        if (name === 'game') QuantHunter.init();
        if (tg) tg.HapticFeedback?.selectionChanged();
      });
    });
  }

  async function fetchPositions() {
    try {
      const paper = await QFApi.paperAccount();
      if (paper.positions?.length) return { positions: paper.positions, source: 'paper' };
    } catch (_) {}
    try {
      const d = await QFApi.positions();
      if (d.positions?.length) return d;
    } catch (_) {}
    return { positions: [], source: 'none' };
  }

  function latestPerAsset(signals) {
    const map = new Map();
    for (const s of signals) {
      const key = `${s.asset}|${s.exchange}`;
      const prev = map.get(key);
      if (!prev || String(s.generated_at) > String(prev.generated_at)) map.set(key, s);
    }
    return [...map.values()];
  }

  function _confBar(conf) {
    const pct = Math.round((conf || 0) * 100);
    const filled = Math.max(0, Math.min(10, Math.round((conf || 0) * 10)));
    return `<span class="ma-conf-bar">${'█'.repeat(filled)}${'░'.repeat(10 - filled)}</span> ${pct}%`;
  }

  function _sigTypeIcon(t) {
    return t === 'LONG' ? '🟢' : t === 'SHORT' ? '🔴' : '⚪';
  }

  async function syncTrade() {
    const dot = document.getElementById('maSyncDot');
    try {
      const [overview, posData, signals, analytics] = await Promise.all([
        QFApi.overview(),
        fetchPositions(),
        QFApi.signals({ limit: 30 }),
        fetch('/api/platform/analytics/summary').then(r => r.json()).catch(() => null),
      ]);
      dot?.classList.add('live');
      const list = posData.positions || [];
      const uniqueSignals = latestPerAsset(signals);

      document.getElementById('maBalance').textContent = QFFmt.money(overview.balance, overview.currency === 'USDT' ? 'USDT' : '₽');
      const pnl = document.getElementById('maPnl');
      if (pnl) {
        pnl.textContent = `PnL ${QFFmt.pct(overview.pnl_day)}`;
        pnl.className = 'ma-hero-sub ' + QFFmt.colorClass(overview.pnl_day);
      }
      document.getElementById('maOpenPos').textContent = String(list.length || overview.open_trades || 0);
      document.getElementById('maSignals').textContent = String(uniqueSignals.length);
      document.getElementById('maSyncTime').textContent = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

      if (analytics && document.getElementById('maWinRate')) {
        document.getElementById('maWinRate').textContent = `${QFFmt.pct(analytics.win_rate)}`;
        document.getElementById('maTotalPnl').textContent = QFFmt.money(analytics.total_pnl, '₽');
        document.getElementById('maTrades').textContent = String(analytics.total_trades || 0);
      }

      document.getElementById('maPositions').innerHTML = list.length
        ? list.map(p => {
          const side = (p.direction || 'long').toUpperCase();
          const pnlVal = p.unrealized_pnl ?? 0;
          return `<div class="ma-row"><div><div class="ma-row-ticker">${p.ticker}</div>
            <div class="ma-row-meta">${p.exchange || posData.source} · ${side}</div></div>
            <span class="${QFFmt.colorClass(pnlVal)}">${pnlVal >= 0 ? '+' : ''}${QFFmt.num(pnlVal)}</span></div>`;
        }).join('')
        : '<div class="ma-empty">Нет позиций</div>';

      document.getElementById('maSignalList').innerHTML = uniqueSignals.length
        ? uniqueSignals.slice(0, 8).map(s => {
          const meta = s.metadata || {};
          const strategy = meta.strategy || '';
          const conf = meta.confidence;
          const regime = meta.regime || '';
          return `<div class="ma-sig-card">
            <div class="ma-sig-top">
              <span class="ma-sig-ticker">${_sigTypeIcon(s.signal_type)} ${s.asset}</span>
              <span class="ma-sig-type ${s.signal_type === 'LONG' ? 'long' : 'short'}">${s.signal_type}</span>
            </div>
            ${strategy ? `<div class="ma-sig-strategy">${strategy}</div>` : ''}
            <div class="ma-sig-bottom">
              ${conf != null ? `<span class="ma-sig-conf">${_confBar(conf)}</span>` : `<span>${s.probability_pct}%</span>`}
              ${regime ? `<span class="ma-sig-regime">${regime}</span>` : ''}
            </div>
          </div>`;
        }).join('')
        : '<div class="ma-empty">Нет сигналов</div>';
    } catch (_) {
      dot?.classList.remove('live');
    }
  }

  function connectSSE() {
    sse = new EventSource('/api/platform/stream');
    sse.addEventListener('trade_executed', syncTrade);
    sse.addEventListener('portfolio_updated', syncTrade);
    sse.addEventListener('signals_updated', syncTrade);
    sse.onerror = () => { sse.close(); setTimeout(connectSSE, 5000); };
  }

  function start(opts = {}) {
    if (started) {
      if (opts.tab === 'game' && activeTab !== 'game') {
        document.querySelector('.ma-tab[data-tab="game"]')?.click();
      }
      return;
    }
    started = true;
    wireTabs();
    syncTrade();
    syncIv = setInterval(syncTrade, 12000);
    connectSSE();

    const tab = opts.tab || (inDashboard ? 'game' : (params.get('tab') === 'game' ? 'game' : 'trade'));
    if (tab === 'game') {
      activeTab = 'game';
      document.querySelectorAll('.ma-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'game'));
      document.querySelectorAll('.ma-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-game'));
      requestAnimationFrame(() => QuantHunter.init());
    } else if (tab === 'trade') {
      activeTab = 'trade';
      document.querySelectorAll('.ma-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'trade'));
      document.querySelectorAll('.ma-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-trade'));
    }
  }

  function stop() {
    if (!started) return;
    started = false;
    if (syncIv) clearInterval(syncIv);
    syncIv = null;
    QuantHunter.destroy();
    sse?.close();
    sse = null;
  }

  window.MiniAppBridge = {
    init: start,
    destroy: stop,
    resize() {},
    syncTrade,
  };

  // Wire prediction overlay buttons (in standalone page)
  document.querySelector('.pred-up')?.addEventListener('click', () => {
    document.getElementById('predictionOverlay')?.querySelectorAll('.pred-up,.pred-down')
      .forEach(b => { if (b.className.includes('up')) b.click(); });
  });

  if (!inDashboard) {
    start({ tab: 'game' });
  }
})();