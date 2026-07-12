/* QuantFlow — Event Sync Layer (SSE + Polling) */

const QFSync = (() => {
  const POLL_MS = 12000;
  let sse = null;
  let pollTimer = null;
  let syncing = false;

  function connect() {
    if (sse) sse.close();
    sse = new EventSource('/api/platform/stream');

    sse.addEventListener('connected', () => {
      QFStore.patch({ sseConnected: true, syncStatus: 'live' });
      updateBadge(true);
    });

    const refresh = (type) => () => handleEvent(type);
    sse.addEventListener('portfolio_updated', refresh('portfolio_updated'));
    sse.addEventListener('signals_updated', refresh('signals_updated'));
    sse.addEventListener('trade_executed', refresh('trade_executed'));
    sse.addEventListener('backtest_complete', refresh('backtest_complete'));

    sse.onerror = () => {
      QFStore.patch({ sseConnected: false, syncStatus: 'reconnecting' });
      updateBadge(false);
      setTimeout(connect, 5000);
    };

    startPolling();
  }

  function updateBadge(live) {
    document.getElementById('wsStatus')?.classList.toggle('online', live);
    const txt = document.getElementById('wsStatusText');
    if (txt) txt.textContent = live ? 'Live' : 'Reconnect';
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => fullSync(false), POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function handleEvent(type) {
    QFStore.emit(`event:${type}`, { type });
    await fullSync(true);
  }

  async function fullSync(force = true) {
    if (syncing && !force) return;
    syncing = true;
    QFStore.patch({ syncStatus: 'syncing' });
    try {
      const [overview, portfolio, positionsRes, paper, signals, stats, equity, market, tinkoff] = await Promise.allSettled([
        QFApi.overview(),
        QFApi.portfolio(),
        QFApi.positions(),
        QFApi.paperAccount(),
        QFApi.signals({ limit: 200 }),
        QFApi.stats(),
        QFApi.equity(),
        QFApi.marketQuotes(),
        QFApi.tinkoffPositions(),
      ]);

      if (overview.status === 'fulfilled') QFStore.patch({ overview: overview.value });
      if (portfolio.status === 'fulfilled') QFStore.patch({ portfolio: portfolio.value });
      if (stats.status === 'fulfilled') QFStore.patch({ stats: stats.value });
      if (equity.status === 'fulfilled') QFStore.patch({ equity: equity.value });
      if (market.status === 'fulfilled') QFStore.patch({ market: market.value });

      const positions = resolvePositions(positionsRes, paper, portfolio, tinkoff);
      QFStore.setPositions(positions.list, positions.source);
      if (paper.status === 'fulfilled') QFStore.patch({ paperPositions: paper.value?.positions || [] });

      if (signals.status === 'fulfilled') QFStore.setSignals(signals.value);

      const ops = buildOperations(
        overview.status === 'fulfilled' ? overview.value : null,
        positions.list,
        signals.status === 'fulfilled' ? signals.value : [],
      );
      QFStore.setOperations(ops);

      QFAssets.rebuild();
      QFStore.patch({ syncStatus: 'live', lastSync: Date.now() });
      QFStore.emit('sync:complete', {});
    } catch (err) {
      QFStore.patch({ syncStatus: 'error' });
      console.warn('[QFSync]', err);
    } finally {
      syncing = false;
    }
  }

  function resolvePositions(positionsRes, paper, portfolio, tinkoff) {
    if (paper.status === 'fulfilled' && paper.value?.positions?.length) {
      return { list: paper.value.positions, source: 'paper' };
    }
    if (positionsRes.status === 'fulfilled' && positionsRes.value?.positions?.length) {
      return { list: positionsRes.value.positions, source: positionsRes.value.source || 'platform' };
    }
    if (tinkoff.status === 'fulfilled' && tinkoff.value?.length) {
      return { list: tinkoff.value, source: 'tinkoff' };
    }
    if (portfolio.status === 'fulfilled') {
      const p = portfolio.value;
      if (p.positions?.length) return { list: p.positions, source: p.source };
      const all = [...(p.best_positions || []), ...(p.worst_positions || [])];
      const seen = new Set();
      const list = all.filter(x => { if (seen.has(x.ticker)) return false; seen.add(x.ticker); return true; });
      if (list.length) return { list, source: p.source };
    }
    return { list: [], source: 'none' };
  }

  function buildOperations(overview, positions, signals) {
    const ops = [];
    (positions || []).forEach(p => {
      const n = QFStore.normalizePosition(p);
      ops.push({
        type: 'open',
        label: 'Open Position',
        ticker: n.ticker,
        exchange: n.exchange,
        direction: n.side,
        pnl: n.unrealized_pnl,
        ts: n.opened_at || new Date().toISOString(),
        status: 'open',
      });
    });
    (overview?.recent_trades || []).forEach(t => {
      ops.push({
        type: t.status === 'open' ? 'open' : 'close',
        label: t.status === 'open' ? 'Open Position' : 'Close Position',
        ticker: t.ticker,
        exchange: t.exchange || '—',
        direction: (t.direction || '').toUpperCase(),
        pnl: t.pnl,
        ts: t.opened_at,
        status: t.status || 'closed',
      });
    });
    (signals || []).filter(s => ['new', 'executing'].includes((s.status || '').toLowerCase())).forEach(s => {
      ops.push({
        type: 'signal',
        label: 'Signal Triggered',
        ticker: s.asset,
        exchange: s.exchange,
        direction: s.signal_type,
        pnl: 0,
        ts: s.generated_at,
        status: s.status,
      });
    });
    ops.sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
    const seen = new Set();
    return ops.filter(o => {
      const k = `${o.type}|${o.ticker}|${o.ts}|${o.label}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    }).slice(0, 50);
  }

  return { connect, fullSync, stopPolling, handleEvent };
})();

window.QFSync = QFSync;