/* QuantFlow — Centralized State + Event Bus */

const QFStore = (() => {
  const bus = new EventTarget();
  const state = {
    overview: null,
    portfolio: null,
    positions: [],
    paperPositions: [],
    signals: [],
    operations: [],
    assets: [],
    watchlist: JSON.parse(localStorage.getItem('qf_watchlist') || '[]'),
    stats: null,
    equity: [],
    market: [],
    syncStatus: 'idle',
    lastSync: null,
    sseConnected: false,
  };

  function emit(type, detail = {}) {
    bus.dispatchEvent(new CustomEvent(type, { detail }));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(`qf:${type}`, { detail }));
    }
  }

  function get() {
    return {
      ...state,
      positions: [...state.positions],
      signals: [...state.signals],
      positionsSource: state.positionsSource,
    };
  }

  function patch(partial) {
    Object.assign(state, partial);
    state.lastSync = Date.now();
    emit('state:updated', { keys: Object.keys(partial) });
  }

  function setPositions(positions, source = 'platform') {
    state.positions = positions.map(normalizePosition);
    state.positionsSource = source;
    emit('positions:updated', { positions: state.positions, source });
  }

  function setSignals(signals) {
    state.signals = dedupeSignals(signals);
    emit('signals:updated', { signals: state.signals });
  }

  function setOperations(ops) {
    state.operations = ops;
    emit('operations:updated', { operations: ops });
  }

  function normalizePosition(p) {
    const qty = p.quantity ?? p.shares ?? 0;
    const entry = p.entry_price ?? p.average_price ?? 0;
    const current = p.current_price ?? entry;
    const pnl = p.unrealized_pnl ?? p.expected_yield ?? p.pnl ?? 0;
    const pnlPct = p.unrealized_pnl_pct ?? p.expected_yield_pct ?? p.pnl_pct ?? 0;
    const direction = (p.direction || (pnl >= 0 && qty > 0 ? 'long' : 'long')).toLowerCase();
    return {
      id: p.id,
      ticker: p.ticker || p.asset || '?',
      exchange: p.exchange || p.source || 'paper',
      direction,
      side: ['long', 'buy'].includes(direction) ? 'LONG' : 'SHORT',
      entry_price: entry,
      current_price: current,
      quantity: qty,
      amount: Math.abs(qty * current),
      leverage: p.leverage ?? 1,
      margin: p.margin ?? (entry * qty),
      unrealized_pnl: pnl,
      unrealized_pnl_pct: pnlPct,
      stop_loss: p.stop_loss ?? null,
      take_profit: p.take_profit ?? p.take_profit_1 ?? null,
      opened_at: p.opened_at ?? null,
      status: p.status || 'open',
      currency: p.currency || 'RUB',
      name: p.name || '',
    };
  }

  function dedupeSignals(signals) {
    const seen = new Set();
    return signals.filter(s => {
      const key = s.id ? `id:${s.id}` : `${s.asset}|${s.exchange}|${s.signal_type}|${s.generated_at}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function toggleWatchlist(ticker) {
    const i = state.watchlist.indexOf(ticker);
    if (i >= 0) state.watchlist.splice(i, 1);
    else state.watchlist.push(ticker);
    localStorage.setItem('qf_watchlist', JSON.stringify(state.watchlist));
    emit('watchlist:updated', { watchlist: [...state.watchlist] });
  }

  function on(type, fn) {
    bus.addEventListener(type, e => fn(e.detail));
    return () => bus.removeEventListener(type, fn);
  }

  return { get, patch, setPositions, setSignals, setOperations, normalizePosition, dedupeSignals, toggleWatchlist, on, emit, bus };
})();

window.QFStore = QFStore;