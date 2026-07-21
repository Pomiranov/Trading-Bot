/* QuantFlow UI Components v2 */

const QFUI = {
  empty(icon, title, desc, action = '') {
    return `<div class="qf-empty empty-state">
      <div class="qf-empty-icon empty-state-icon">${icon}</div>
      <div class="qf-empty-title empty-state-title">${title}</div>
      <div class="qf-empty-desc empty-state-desc">${desc}</div>
      ${action ? `<div class="qf-empty-action">${action}</div>` : ''}
    </div>`;
  },

  skeleton(type = 'value') {
    if (type === 'grid') {
      return Array(6).fill('<div class="metric-mini skeleton-block"></div>').join('');
    }
    return `<span class="skeleton skeleton-${type}"></span>`;
  },

  badge(type) {
    const t = (type || '').toUpperCase();
    const map = {
      BUY: 'badge-buy', LONG: 'badge-buy',
      SELL: 'badge-sell', SHORT: 'badge-sell',
      HOLD: 'badge-hold', NEW: 'badge-info',
      EXECUTING: 'badge-warn', CLOSED: 'badge-hold',
    };
    return `<span class="badge ${map[t] || 'badge-hold'}">${t}</span>`;
  },

  metricTile(label, value, cls = '', sub = '') {
    return `<div class="metric-mini qf-metric">
      <div class="metric-mini-label">${label}</div>
      <div class="metric-mini-value ${cls}">${value}</div>
      ${sub ? `<div class="metric-mini-sub">${sub}</div>` : ''}
    </div>`;
  },

  statusDot(ok) {
    return `<span class="status-dot-inline ${ok ? 'online' : ''}"></span>`;
  },

  progressBar(pct, cls = '') {
    const p = Math.min(100, Math.max(0, pct));
    return `<div class="qf-progress ${cls}"><div class="qf-progress-fill" style="width:${p}%"></div></div>`;
  },

  allocationList(items, max = 6) {
    if (!items?.length) return '<div class="empty">Нет данных</div>';
    const colors = ['#F7931A', '#3861fb', '#00c076', '#f6465d', '#8b5cf6', '#06b6d4'];
    return `<div class="alloc-list">${items.slice(0, max).map((a, i) => `
      <div class="alloc-row">
        <span class="alloc-dot" style="background:${colors[i % colors.length]}"></span>
        <span class="alloc-label">${a.label}</span>
        <span class="alloc-bar-wrap">${QFUI.progressBar(a.pct)}</span>
        <span class="alloc-pct">${a.pct}%</span>
      </div>`).join('')}</div>`;
  },

  logBadge(level) {
    const l = (level || '').toUpperCase();
    if (l === 'ERROR') return '<span class="badge badge-error">ERR</span>';
    if (l === 'WARN' || l === 'WARNING') return '<span class="badge badge-warn">WARN</span>';
    return '<span class="badge badge-info">INFO</span>';
  },

  positionTableRow(p) {
    const n = QFStore?.normalizePosition ? QFStore.normalizePosition(p) : p;
    const cls = QFFmt.colorClass(n.unrealized_pnl);
    const side = QFFmt.sideBadge(n.direction);
    return `<tr class="pos-row">
      <td class="ticker-cell sticky-col">${n.ticker}</td>
      <td>${n.exchange}</td>
      <td>${side}</td>
      <td class="mono">${QFFmt.num(n.entry_price)}</td>
      <td class="mono">${QFFmt.num(n.current_price)}</td>
      <td class="mono">${QFFmt.int(n.quantity)}</td>
      <td class="mono">${n.leverage}x</td>
      <td class="mono">${QFFmt.compact(n.margin)}</td>
      <td class="mono ${cls}">${n.unrealized_pnl >= 0 ? '+' : ''}${QFFmt.num(n.unrealized_pnl)}</td>
      <td class="mono ${cls}">${QFFmt.pct(n.unrealized_pnl_pct)}</td>
      <td class="mono">${n.stop_loss ? QFFmt.num(n.stop_loss) : '—'}</td>
      <td class="mono">${n.take_profit ? QFFmt.num(n.take_profit) : '—'}</td>
      <td class="ts-cell">${QFFmt.ts(n.opened_at)}</td>
      <td><span class="badge badge-info">${n.status}</span></td>
    </tr>`;
  },

  opsTableRow(o) {
    const typeMap = {
      open: 'badge-buy', close: 'badge-sell', signal: 'badge-warn',
      'Open Position': 'badge-buy', 'Close Position': 'badge-sell', 'Signal Triggered': 'badge-warn',
    };
    const label = o.label || o.type;
    const cls = QFFmt.colorClass(o.pnl);
    return `<tr>
      <td class="ts-cell">${QFFmt.ts(o.ts)}</td>
      <td><span class="badge ${typeMap[label] || 'badge-info'}">${label}</span></td>
      <td class="ticker-cell">${o.ticker}</td>
      <td>${o.exchange || '—'}</td>
      <td>${QFUI.badge((o.direction || '').toUpperCase())}</td>
      <td class="mono ${cls}">${o.pnl ? (o.pnl >= 0 ? '+' : '') + QFFmt.num(o.pnl) : '—'}</td>
      <td><span class="badge badge-hold">${o.status || '—'}</span></td>
    </tr>`;
  },

  loading(text = 'Загрузка…') {
    return `<div class="qf-loading"><div class="qf-spinner"></div><span>${text}</span></div>`;
  },

  positionRow(p) {
    const cls = (p.unrealized_pnl ?? p.expected_yield ?? 0) >= 0 ? 'positive' : 'negative';
    const pnl = p.unrealized_pnl ?? p.expected_yield ?? 0;
    const pctVal = p.unrealized_pnl_pct ?? p.expected_yield_pct ?? 0;
    const qty = p.quantity ?? p.shares ?? 0;
    const entry = p.entry_price ?? p.average_price ?? 0;
    const name = p.name ? `<div class="pos-name">${p.name}</div>` : '';
    return `<div class="position-row">
      <div class="pos-top">
        <span class="pos-ticker">${p.ticker}</span>
        <span class="pos-pnl ${cls}">${pnl >= 0 ? '+' : ''}${typeof fmt !== 'undefined' ? fmt.format(pnl) : pnl}</span>
      </div>
      ${name}
      <div class="pos-meta">
        <span>${typeof fmtInt !== 'undefined' ? fmtInt.format(qty) : qty} шт · ${typeof fmt !== 'undefined' ? fmt.format(entry) : entry}</span>
        <span class="${cls}">${typeof pct !== 'undefined' ? pct(pctVal) : pctVal + '%'}</span>
      </div>
    </div>`;
  },

  signalCard(s, showAction = true, dupCount = 0) {
    const t = (s.signal_type || s.action || '').toUpperCase();
    const typeCls = ['BUY', 'LONG'].includes(t) ? 'type-long' : ['SELL', 'SHORT'].includes(t) ? 'type-short' : '';
    const prob = s.probability_pct || 50;
    const price = s.entry_price ?? s.price ?? 0;
    const rr = s.risk_reward ? Number(s.risk_reward).toFixed(1) + 'R' : '—';
    const fmtN = typeof fmt !== 'undefined' ? (v) => fmt.format(v) : (v) => String(v);
    const dupBadge = dupCount > 1 ? `<span class="signal-dup-badge" title="${dupCount} сигналов для этого паттерна">×${dupCount}</span>` : '';
    return `<div class="signal-card ${typeCls}">
      <div class="signal-card-header">
        <div class="signal-card-left">
          <span class="indicator-ticker">${s.asset || s.ticker}${dupBadge}</span>
          <span class="signal-exchange">${s.exchange || '—'} · ${s.source || '—'}</span>
        </div>
        ${QFUI.badge(t)}
      </div>
      <div class="signal-price">${fmtN(price)}</div>
      <div class="signal-grid-mini">
        <div class="signal-stat"><span>RR</span><strong>${rr}</strong></div>
        <div class="signal-stat"><span>SL</span><strong class="negative">${s.stop_loss ? fmtN(s.stop_loss) : '—'}</strong></div>
        <div class="signal-stat"><span>TP1</span><strong class="positive">${s.take_profit_1 ? fmtN(s.take_profit_1) : '—'}</strong></div>
        <div class="signal-stat"><span>TP2</span><strong class="positive">${s.take_profit_2 ? fmtN(s.take_profit_2) : '—'}</strong></div>
      </div>
      <div class="signal-prob-row">
        <span>Уверенность <strong style="color:var(--qf-text)">${prob}%</strong></span>
        <div class="prob-bar"><div class="prob-bar-fill" style="width:${prob}%"></div></div>
      </div>
      ${showAction && s.id ? `<button class="btn btn-sm btn-primary btn-action signal-open-btn" onclick="executeSignal(${s.id})">Открыть позицию</button>` : ''}
    </div>`;
  },

  /* ── Toast notifications ── */
  toast(message, type = 'info', duration = 4000) {
    let root = document.getElementById('toastRoot');
    if (!root) {
      root = document.createElement('div');
      root.id = 'toastRoot';
      root.className = 'toast-root';
      document.body.appendChild(root);
    }
    const icons = { success: '✓', error: '✕', warn: '⚠', info: 'ℹ' };
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast-icon';
    iconSpan.textContent = icons[type] || icons.info;
    const msgSpan = document.createElement('span');
    msgSpan.className = 'toast-msg';
    msgSpan.textContent = message;
    el.append(iconSpan, msgSpan);
    root.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 300);
    }, duration);
  },

  confirm(message) {
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = `
        <div class="modal-card">
          <div class="modal-title">Подтверждение</div>
          <div class="modal-body"></div>
          <div class="modal-actions">
            <button class="btn btn-ghost" data-action="cancel">Отмена</button>
            <button class="btn btn-primary" data-action="ok">Подтвердить</button>
          </div>
        </div>`;
      overlay.querySelector('.modal-body').textContent = message;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add('show'));
      overlay.addEventListener('click', e => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        overlay.classList.remove('show');
        setTimeout(() => overlay.remove(), 200);
        resolve(btn.dataset.action === 'ok');
      });
    });
  },
};

window.QFUI = QFUI;
window.toast = (msg, type) => QFUI.toast(msg, type);