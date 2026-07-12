/* QuantFlow — Dynamic Asset Management */

const QFAssets = (() => {
  let assets = [];

  function rebuild() {
    const s = QFStore.get();
    const map = new Map();

    (s.market || []).forEach(q => {
      map.set(q.ticker, {
        ticker: q.ticker,
        price: q.price,
        change_1d: q.change_1d,
        volume: q.volume,
        type: guessType(q.ticker),
        exchange: guessExchange(q.ticker),
      });
    });

    (s.positions || []).forEach(p => {
      if (!map.has(p.ticker)) {
        map.set(p.ticker, { ticker: p.ticker, price: p.current_price, change_1d: p.unrealized_pnl_pct, type: guessType(p.ticker), exchange: p.exchange });
      }
    });

    (s.signals || []).forEach(sig => {
      if (!map.has(sig.asset)) {
        map.set(sig.asset, { ticker: sig.asset, price: sig.entry_price, change_1d: 0, type: sig.asset_class || 'stocks', exchange: sig.exchange });
      }
    });

    assets = [...map.values()].sort((a, b) => a.ticker.localeCompare(b.ticker));
    QFStore.patch({ assets });
    QFStore.emit('assets:updated', { assets });
    return assets;
  }

  function guessType(ticker) {
    if (/USDT|BTC|ETH|USD$/.test(ticker)) return 'crypto';
    if (ticker.length <= 5 && ticker === ticker.toUpperCase()) return 'stocks';
    return 'stocks';
  }

  function guessExchange(ticker) {
    if (/USDT/.test(ticker)) return 'bybit';
    return 'moex';
  }

  function search(query) {
    const q = (query || '').trim().toUpperCase();
    if (!q) return assets;
    return assets.filter(a => a.ticker.toUpperCase().includes(q) || (a.exchange || '').toUpperCase().includes(q));
  }

  function watchlist() {
    const wl = QFStore.get().watchlist;
    return assets.filter(a => wl.includes(a.ticker));
  }

  function favorites() { return watchlist(); }

  return { rebuild, search, watchlist, favorites, all: () => assets };
})();

window.QFAssets = QFAssets;