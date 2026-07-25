/* QuantFlow — Formatters */

const QFFmt = (() => {
  const moneyFmt = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const intFmt = new Intl.NumberFormat('ru-RU');
  const compactFmt = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 });

  function money(v, cur = '₽') {
    if (v == null || isNaN(v)) return '—';
    return moneyFmt.format(v) + (cur === 'USDT' ? ' USDT' : ` ${cur}`);
  }

  function pct(v, signed = true) {
    if (v == null || isNaN(v)) return '—';
    const n = Object.is(v, -0) ? 0 : v;
    return (signed && n > 0 ? '+' : '') + moneyFmt.format(n) + '%';
  }

  function num(v, digits = 2) {
    if (v == null || isNaN(v)) return '—';
    return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
  }

  function int(v) { return v == null ? '—' : intFmt.format(v); }
  function compact(v) { return v == null ? '—' : compactFmt.format(v); }

  function colorClass(v) {
    if (v > 0) return 'positive';
    if (v < 0) return 'negative';
    return 'neutral';
  }

  function sideBadge(direction) {
    const d = (direction || 'long').toLowerCase();
    const isLong = d === 'long' || d === 'buy';
    return `<span class="badge ${isLong ? 'badge-long' : 'badge-short'}">${isLong ? 'LONG' : 'SHORT'}</span>`;
  }

  function ts(v) {
    if (!v) return '—';
    return String(v).slice(0, 19).replace('T', ' ');
  }

  return { money, pct, num, int, compact, colorClass, sideBadge, ts };
})();

window.QFFmt = QFFmt;
window.fmt = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
window.fmtInt = new Intl.NumberFormat('ru-RU');
window.money = (v) => QFFmt.money(v);
window.pct = (v) => QFFmt.pct(v);
window.colorClass = QFFmt.colorClass;