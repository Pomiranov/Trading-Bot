/* QuantFlow — View Renderers */

const QFRender = (() => {
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

  function applyColor(el, v) {
    if (!el) return;
    el.classList.remove('positive', 'negative', 'neutral');
    el.classList.add(QFFmt.colorClass(v));
  }

  function sourceLabel(source) {
    const map = { paper: 'Paper', broker: 'Broker', tinkoff: 'Т-Банк', bybit: 'Bybit' };
    return map[source] || (source || 'Platform').toUpperCase();
  }

  /* ── Dashboard ── */
  function dashboard(state) {
    const { overview, portfolio, stats, positions, signals, equity } = state;

    // overview is one of several independent API calls (see QFSync.fullSync) —
    // if only it fails, the rest of this function must still render whatever
    // portfolio/stats/equity/signals data did come back, instead of leaving
    // every card stuck on its loading skeleton.
    if (overview) {
      const cur = overview.currency === 'USDT' ? 'USDT' : '₽';
      const src = document.getElementById('heroSource');
      if (src) {
        src.textContent = sourceLabel(portfolio?.source);
        src.className = 'badge ' + (portfolio?.source === 'paper' ? 'badge-warn' : 'badge-buy');
      }

      const bal = document.getElementById('metPortfolio');
      if (bal) { bal.className = 'hero-value neutral'; animateValue(bal, overview.balance, v => QFFmt.money(v, cur)); }

      const trades = document.getElementById('metTrades');
      if (trades) trades.textContent = `${overview.open_trades} открытых · ${overview.closed_trades} закрытых`;

      const pnl = document.getElementById('metPnl');
      if (pnl) { animateValue(pnl, overview.pnl_day, v => (v >= 0 ? '+' : '') + QFFmt.money(v)); applyColor(pnl, overview.pnl_day); }

      const pnlPct = document.getElementById('metPnlPct');
      if (pnlPct) pnlPct.textContent = `${overview.signals_new} новых сигналов`;

      renderBrokers(overview.brokers);
      renderSystem(overview.system, overview.websocket_status);
      renderRecent('recentTradesList', overview.recent_trades, t =>
        `<div class="recent-item"><span class="recent-ticker">${t.ticker}</span><span class="${QFFmt.colorClass(t.pnl)}">${QFFmt.num(t.pnl)}</span></div>`);
      renderRecent('recentSignalsList', overview.recent_signals, s =>
        `<div class="recent-item"><span class="recent-ticker">${s.asset}</span>${QFUI.badge(s.signal_type)}</div>`);
      renderRecent('recentErrorsList', overview.recent_errors, e =>
        `<div class="recent-item">${QFUI.logBadge(e.level)}<span class="log-msg">${(e.message || '').slice(0, 40)}</span></div>`);
    }

    if (portfolio) {
      ['dashPnlWeek', 'dashPnlMonth'].forEach((id, i) => {
        const el = document.getElementById(id);
        const v = i === 0 ? portfolio.pnl_week : portfolio.pnl_month;
        if (el) { el.textContent = (v >= 0 ? '+' : '') + QFFmt.money(v); applyColor(el, v); }
      });
      if (portfolio.equity_history?.length) {
        QFChart.line('heroSparkline', portfolio.equity_history.map(h => ({ time: h.ts, value: h.equity })), { color: '#F7931A', fill: 'rgba(247,147,26,0.15)' });
      }
      updateRiskPanel(portfolio, stats);
    }

    if (stats) {
      const ddVal = stats.max_drawdown != null ? Math.abs(stats.max_drawdown) : null;
      const dd = document.getElementById('metDrawdown');
      if (dd && ddVal != null) {
        dd.textContent = '-' + ddVal.toFixed(1) + '%';
        applyColor(dd, -ddVal);
        // Update gauge color — green <5%, orange 5-15%, red >15%
        const gauge = dd.closest('.qf-gauge');
        if (gauge) {
          gauge.style.setProperty('--gauge-value', Math.min(ddVal * 5, 100));
          gauge.style.setProperty('--gauge-color', ddVal < 5 ? 'var(--qf-long)' : ddVal < 15 ? 'var(--qf-accent)' : 'var(--qf-short)');
        }
      }
      const wr = document.getElementById('metWinRate');
      if (wr && stats.win_rate != null) wr.textContent = 'Win ' + stats.win_rate.toFixed(1) + '%';
      const sh = document.getElementById('metSharpe');
      if (sh && stats.sharpe_ratio != null) { sh.textContent = stats.sharpe_ratio.toFixed(2); sh.className = 'metric-value ' + QFFmt.colorClass(stats.sharpe_ratio); }
    }

    renderDashboardPositions(positions);
    renderDashboardSignals(signals);

    if (equity?.length) {
      QFChart.line('equityChart', equity.map(d => ({ time: d.ts, value: d.equity })));
      const first = equity[0]?.equity || 0, last = equity[equity.length - 1]?.equity || 0;
      const diff = last - first, diffP = first ? diff / first * 100 : 0;
      const sub = document.getElementById('chartSubtitle');
      if (sub) {
        sub.textContent = `${equity.length} точек · ${diff >= 0 ? '+' : ''}${QFFmt.num(diff)} ₽ (${QFFmt.pct(diffP)})`;
        sub.className = 'card-subtitle ' + (diff >= 0 ? 'sub-positive' : 'sub-negative');
      }
    }

    setBotStatus('live');
    const lu = document.getElementById('lastUpdated');
    if (lu) lu.textContent = 'обновлено ' + new Date().toLocaleTimeString('ru-RU', { hour12: false });
  }

  function renderDashboardPositions(positions) {
    const list = document.getElementById('positionsList');
    const cnt = document.getElementById('posCount');
    if (!list) return;
    if (!positions?.length) {
      if (cnt) cnt.textContent = '0';
      list.innerHTML = QFUI.empty('📭', 'Нет позиций', 'Откройте сделку через Signals', '<button class="btn btn-secondary btn-action" onclick="showView(\'signals\')">К сигналам</button>');
      return;
    }
    if (cnt) cnt.textContent = String(positions.length);
    list.innerHTML = positions.map(p => QFUI.positionRow(p)).join('');
  }

  function renderDashboardSignals(signals) {
    const tbody = document.getElementById('signalsBody');
    if (!tbody) return;
    const data = (signals || []).slice(0, 15);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">Нет сигналов</td></tr>'; return; }
    tbody.innerHTML = data.map(s => `
      <tr>
        <td class="ts-cell">${QFFmt.ts(s.generated_at)}</td>
        <td class="ticker-cell">${s.asset}</td>
        <td>${QFUI.badge(s.signal_type)}</td>
        <td class="price-cell">${QFFmt.num(s.entry_price)}</td>
        <td>${s.probability_pct ?? '—'}%</td>
      </tr>`).join('');
    const su = document.getElementById('signalsUpdated');
    if (su) su.textContent = new Date().toLocaleTimeString('ru-RU', { hour12: false });
  }

  function updateRiskPanel(portfolio, stats) {
    if (!portfolio || typeof setRiskBar !== 'function') return;
    const balance = portfolio.total_balance || 1;
    const unreal = portfolio.unrealized_pnl || 0;
    setRiskBar('riskDailyBar', 'riskDailyVal', Math.min(Math.abs(unreal) / balance * 100, 100), (unreal >= 0 ? '+' : '') + QFFmt.money(unreal), 25, 50);
    const dd = Math.abs(stats?.max_drawdown || 0);
    setRiskBar('riskDdBar', 'riskDdVal', Math.min(dd, 100), QFFmt.pct(-dd), 10, 20);
    const maxPos = window._maxOpenPositions || 10;
    const posCount = portfolio.open_positions_count || 0;
    setRiskBar('riskPosBar', 'riskPosVal', Math.min(posCount / maxPos * 100, 100), `${posCount}/${maxPos}`, 70, 90);
    setRiskBar('riskWrBar', 'riskWrVal', stats?.win_rate ?? 0, QFFmt.num(stats?.win_rate ?? 0) + '%', 0, 0);
  }

  function renderBrokers(brokers) {
    const el = document.getElementById('brokersPanel');
    if (!el) return;
    if (!brokers?.length) { el.innerHTML = QFUI.empty('🏦', 'Брокеры', 'Нет данных'); return; }
    el.innerHTML = brokers.map(b => `
      <div class="broker-row">${QFUI.statusDot(b.connected)}<span class="broker-name">${b.name}</span>
      <span class="broker-status ${b.connected ? 'positive' : 'negative'}">${b.connected ? 'Online' : b.configured ? 'Error' : 'Offline'}</span></div>`).join('');
  }

  function renderSystem(sys, wsStatus) {
    const el = document.getElementById('systemPanel');
    if (!el || !sys) return;
    const cpu = sys.cpu_percent || 0, ram = sys.ram?.percent || 0;
    const bar = (v) => QFUI.progressBar(v, v >= 85 ? 'danger' : v >= 65 ? 'warn' : '');
    el.innerHTML = `<div class="system-grid">
      <div class="system-item"><span class="system-label">CPU</span><span class="system-val">${cpu}%</span><div class="system-bar">${bar(cpu)}</div></div>
      <div class="system-item"><span class="system-label">RAM</span><span class="system-val">${ram}%</span><div class="system-bar">${bar(ram)}</div></div>
      <div class="system-item"><span class="system-label">Database</span><span class="system-val ${sys.database?.connected ? 'positive' : 'negative'}">${sys.database?.status || '—'}</span></div>
      <div class="system-item"><span class="system-label">API</span><span class="system-val positive">${sys.api?.status || 'online'}</span></div>
      <div class="system-item"><span class="system-label">Telegram</span><span class="system-val">${sys.telegram?.status || '—'}</span></div>
      <div class="system-item"><span class="system-label">SSE</span><span class="system-val ${QFStore.get().sseConnected ? 'positive' : ''}">${QFStore.get().sseConnected ? 'Live' : 'Offline'}</span></div>
      <div class="system-item"><span class="system-label">Docker</span><span class="system-val">${(sys.docker?.containers || []).length}</span></div>
      <div class="system-item"><span class="system-label">Disk</span><span class="system-val">${sys.disk_free_gb}G</span></div>
      <div class="system-item"><span class="system-label">Redis</span><span class="system-val">${sys.redis?.status || '—'}</span></div>
    </div>`;
  }

  function renderRecent(id, items, fn) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!items?.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    el.innerHTML = items.slice(0, 8).map(fn).join('');
  }

  /* ── Portfolio ── */
  function portfolio(state) {
    const { portfolio: p, positions, operations, assets } = state;
    if (!p) return;

    const posCount = positions?.length ?? p.open_positions_count ?? 0;
    const srcType = state.positionsSource || p.source;

    const src = document.getElementById('portfolioSource');
    if (src) { src.textContent = sourceLabel(srcType); src.className = 'badge ' + (srcType === 'paper' ? 'badge-warn' : 'badge-buy'); }

    const grid = document.getElementById('portfolioMetrics');
    if (grid) {
      const unrealized = positions?.length
        ? positions.reduce((s, x) => s + (x.unrealized_pnl ?? 0), 0)
        : p.unrealized_pnl;
      const metrics = [
        ['Баланс', QFFmt.money(p.total_balance), ''], ['Доступно', QFFmt.money(p.available_funds), ''],
        ['Маржа', QFFmt.money(p.margin_used), ''], ['PnL', (p.total_pnl >= 0 ? '+' : '') + QFFmt.money(p.total_pnl), QFFmt.colorClass(p.total_pnl)],
        ['День', (p.pnl_day >= 0 ? '+' : '') + QFFmt.money(p.pnl_day), QFFmt.colorClass(p.pnl_day)],
        ['Неделя', (p.pnl_week >= 0 ? '+' : '') + QFFmt.money(p.pnl_week), QFFmt.colorClass(p.pnl_week)],
        ['Месяц', (p.pnl_month >= 0 ? '+' : '') + QFFmt.money(p.pnl_month), QFFmt.colorClass(p.pnl_month)],
        ['ROI', QFFmt.pct(p.roi), QFFmt.colorClass(p.roi)],
        ['Unrealized', QFFmt.money(unrealized), QFFmt.colorClass(unrealized)],
        ['Позиций', posCount, ''], ['Сделок', p.closed_trades_count, ''],
      ];
      grid.innerHTML = metrics.map(([l, v, c]) => QFUI.metricTile(l, v, c)).join('');
    }

    renderPositionsPanel(positions);
    renderPositionsTable(positions);
    renderOpsTable(operations);

    const sorted = [...(positions || [])].sort((a, b) => (b.unrealized_pnl ?? 0) - (a.unrealized_pnl ?? 0));
    renderHighlights('bestPositions', p.best_positions?.length ? p.best_positions : sorted.slice(0, 3));
    renderHighlights('worstPositions', p.worst_positions?.length ? p.worst_positions : [...sorted].reverse().slice(0, 3));

    const allocList = document.getElementById('allocationList');
    if (allocList) allocList.innerHTML = QFUI.allocationList(p.asset_allocation || []);
    const currencyList = document.getElementById('currencyList');
    if (currencyList) currencyList.innerHTML = QFUI.allocationList(p.currency_allocation || []);

    QFChart.pie('allocationChart', p.asset_allocation || []);
    QFChart.pie('currencyChart', p.currency_allocation || []);
    QFChart.line('portfolioEquityChart', (p.equity_history || []).map(h => ({ time: h.ts, value: h.equity })));

    renderAssetPanel(assets);
    document.getElementById('portfolioUpdated')?.replaceChildren(document.createTextNode(new Date().toLocaleTimeString('ru-RU', { hour12: false })));
  }

  function renderPositionsPanel(positions) {
    const el = document.getElementById('portfolioPositions');
    if (!el) return;
    if (!positions?.length) {
      el.innerHTML = QFUI.empty('📭', 'Нет открытых позиций', 'Сделки из Telegram и Dashboard синхронизируются автоматически');
      return;
    }
    el.innerHTML = positions.map(p => QFUI.positionRow(p)).join('');
  }

  function renderPositionsTable(positions) {
    const tbody = document.getElementById('portfolioPositionsTable');
    if (!tbody) return;
    if (!positions?.length) {
      tbody.innerHTML = '<tr><td colspan="14" class="empty">Нет открытых позиций</td></tr>';
      return;
    }
    tbody.innerHTML = positions.map(p => QFUI.positionTableRow(p)).join('');
  }

  function renderOpsTable(operations) {
    const tbody = document.getElementById('portfolioOpsTable');
    const meta = document.getElementById('opsHistoryMeta');
    if (!tbody) return;
    if (!operations?.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">Нет операций</td></tr>';
      if (meta) meta.textContent = '';
      return;
    }
    if (meta) meta.textContent = `${operations.length} записей`;
    tbody.innerHTML = operations.map(o => QFUI.opsTableRow(o)).join('');
  }

  function renderHighlights(id, items) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!items?.length) { el.innerHTML = '<div class="empty">—</div>'; return; }
    el.innerHTML = items.map(p => QFUI.positionRow(p)).join('');
  }

  function renderAssetPanel(assets) {
    const grid = document.getElementById('tickerGrid');
    const search = document.getElementById('assetSearch')?.value || '';
    const list = search ? QFAssets.search(search) : (assets || []);
    const wl = QFStore.get().watchlist;

    if (grid) {
      if (!list.length) { grid.innerHTML = '<div class="empty">Нет инструментов</div>'; return; }
      grid.innerHTML = list.map(a => {
        const fav = wl.includes(a.ticker);
        const cls = (a.change_1d || 0) >= 0 ? 'positive' : 'negative';
        return `<div class="ticker-card" onclick="loadTickerChart('${a.ticker}')">
          <div class="ticker-card-top"><span class="ticker-card-symbol">${a.ticker}</span>
          <button class="watchlist-btn ${fav ? 'active' : ''}" onclick="event.stopPropagation();QFStore.toggleWatchlist('${a.ticker}');QFRender.portfolio(QFStore.get())" type="button">${fav ? '★' : '☆'}</button></div>
          <div class="ticker-card-exchange">${a.exchange || '—'} · ${a.type || '—'}</div>
          <div class="ticker-card-price">${QFFmt.num(a.price)}</div>
          <div class="ticker-card-change ${cls}">${QFFmt.pct(a.change_1d || 0)}</div></div>`;
      }).join('');
    }

    const watch = document.getElementById('watchlistGrid');
    if (watch) {
      const favs = QFAssets.watchlist();
      watch.innerHTML = favs.length
        ? favs.map(a => `<button class="watchlist-chip" onclick="loadTickerChart('${a.ticker}')">${a.ticker}</button>`).join('')
        : '<span class="empty-inline">Добавьте в избранное</span>';
    }
  }

  /* ── Signals ── */
  function latestPerAsset(signals) {
    const map = new Map();
    for (const s of signals || []) {
      const key = `${s.asset}|${s.exchange}`;
      const prev = map.get(key);
      if (!prev || String(s.generated_at) > String(prev.generated_at)) map.set(key, s);
    }
    return [...map.values()].sort((a, b) => String(b.generated_at).localeCompare(String(a.generated_at)));
  }

  function filterSignals(signals) {
    const exchange = document.getElementById('filterExchange')?.value || '';
    const assetClass = document.getElementById('filterAssetClass')?.value || '';
    const strategy = document.getElementById('filterStrategy')?.value || '';
    const direction = document.getElementById('filterDirection')?.value || '';
    const asset = (document.getElementById('filterAsset')?.value || '').trim().toUpperCase();
    const dateFrom = document.getElementById('filterDateFrom')?.value || '';

    return (signals || []).filter(s => {
      if (exchange && s.exchange !== exchange) return false;
      if (assetClass && s.asset_class !== assetClass) return false;
      if (strategy && s.source !== strategy) return false;
      if (direction) {
        const t = (s.signal_type || '').toUpperCase();
        const map = { LONG: ['BUY', 'LONG'], SHORT: ['SELL', 'SHORT'], BUY: ['BUY', 'LONG'], SELL: ['SELL', 'SHORT'] };
        if (!map[direction]?.includes(t)) return false;
      }
      if (asset && !(s.asset || '').toUpperCase().includes(asset)) return false;
      if (dateFrom && String(s.generated_at).slice(0, 10) < dateFrom) return false;
      return true;
    });
  }

  function signals(state) {
    const data = filterSignals(state.signals);
    const grid = document.getElementById('indicatorsGrid');
    const tbody = document.getElementById('signalsLiveBody');
    const statsEl = document.getElementById('signalsStats');

    if (statsEl) {
      const long = data.filter(s => ['BUY', 'LONG'].includes((s.signal_type || '').toUpperCase())).length;
      const short = data.filter(s => ['SELL', 'SHORT'].includes((s.signal_type || '').toUpperCase())).length;
      const fresh = data.filter(s => ['new', 'executing'].includes((s.status || '').toLowerCase())).length;
      statsEl.innerHTML = `
        <div class="signal-stat-pill">Всего <strong>${data.length}</strong></div>
        <div class="signal-stat-pill">Long <strong class="positive">${long}</strong></div>
        <div class="signal-stat-pill">Short <strong class="negative">${short}</strong></div>
        <div class="signal-stat-pill">Активные <strong>${fresh}</strong></div>`;
    }

    renderTriggeredRules(data);

    if (!data.length) {
      if (grid) grid.innerHTML = QFUI.empty('📡', 'Нет сигналов', 'Измените фильтры или сгенерируйте новые');
      if (tbody) tbody.innerHTML = '<tr><td colspan="13" class="empty">Нет сигналов</td></tr>';
      return;
    }

    // Count how many raw signals exist per asset key for the count badge
    const countPerKey = new Map();
    for (const s of data) {
      const key = `${s.asset}|${s.exchange}`;
      countPerKey.set(key, (countPerKey.get(key) || 0) + 1);
    }
    const cards = latestPerAsset(data);
    if (grid) grid.innerHTML = cards.slice(0, 16).map(s => {
      const key = `${s.asset}|${s.exchange}`;
      const cnt = countPerKey.get(key) || 1;
      return QFUI.signalCard(s, true, cnt > 1 ? cnt : 0);
    }).join('');
    if (tbody) {
      tbody.innerHTML = data.map(s => {
        const tp1 = s.take_profit_1 ? QFFmt.num(s.take_profit_1) : '—';
        const tp2 = s.take_profit_2 ? QFFmt.num(s.take_profit_2) : '—';
        const tp3 = s.take_profit_3 ? QFFmt.num(s.take_profit_3) : '—';
        const tpCell = s.take_profit_2
          ? `<span title="TP1: ${tp1} · TP2: ${tp2} · TP3: ${tp3}">${tp1}<span class="tp-more">+2</span></span>`
          : tp1;
        const rr = s.risk_reward ? Number(s.risk_reward).toFixed(1) + 'R' : '—';
        const prob = s.probability_pct != null ? `${s.probability_pct}%` : '—';
        const statusClass = { new: 'badge-info', executing: 'badge-warn', done: 'badge-buy', filled: 'badge-buy', expired: 'badge-hold', cancelled: 'badge-error' }[(s.status || '').toLowerCase()] || 'badge-hold';
        return `<tr>
          <td class="ticker-cell">${s.asset}</td><td>${s.exchange}</td><td>${s.source || '—'}</td>
          <td>${QFUI.badge(s.signal_type)}</td><td class="price-cell">${QFFmt.num(s.entry_price)}</td>
          <td class="price-cell negative">${s.stop_loss ? QFFmt.num(s.stop_loss) : '—'}</td>
          <td class="price-cell positive">${tpCell}</td>
          <td class="price-cell">${rr}</td><td>${prob}</td>
          <td class="ts-cell">${QFFmt.ts(s.generated_at)}</td>
          <td><span class="badge ${statusClass}">${s.status}</span></td>
          <td><button class="btn btn-sm btn-ghost" onclick="executeSignal(${s.id})" title="Execute as paper trade">▶</button></td>
        </tr>`;
      }).join('');
    }
    document.getElementById('signalsLiveUpdated')?.replaceChildren(document.createTextNode(`${data.length} сигналов`));
  }

  function renderTriggeredRules(data) {
    const card = document.getElementById('triggeredRulesCard');
    const body = document.getElementById('triggeredRulesBody');
    if (!card || !body) return;
    const withRules = data.filter(s => s.metadata?.triggered?.length);
    if (!withRules.length) { card.style.display = 'none'; return; }
    card.style.display = 'block';
    body.innerHTML = withRules.slice(0, 8).map(s =>
      `<div class="recent-item"><span class="recent-ticker">${s.asset}</span><span class="ts-cell">${(s.metadata.triggered || []).join(', ')}</span></div>`
    ).join('');
  }

  /* ── Backtest metrics fix ── */
  function backtestMetrics(metrics) {
    const el = document.getElementById('backtestMetrics');
    if (!el) return;
    el.innerHTML = metrics.map(([l, v]) => QFUI.metricTile(l, v)).join('');
  }

  function refreshCurrentView() {
    const s = QFStore.get();
    if (currentView === 'dashboard') dashboard(s);
    else if (currentView === 'portfolio') portfolio(s);
    else if (currentView === 'signals') signals(s);
  }

  return { dashboard, portfolio, signals, backtestMetrics, refreshCurrentView, filterSignals, renderAssetPanel, animateValue, applyColor };
})();

window.QFRender = QFRender;