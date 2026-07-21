/* QuantFlow — Learning Dashboard View */
'use strict';

(function () {

  // ─── State ───────────────────────────────────────────────────────────────────
  let _hyp_stage_filter = '';
  let _refresh_timer = null;
  const REFRESH_INTERVAL = 20_000;

  // ─── Utilities ───────────────────────────────────────────────────────────────
  function conf_bar(v) {
    const pct = Math.round((v || 0) * 100);
    const cls = v >= 0.6 ? 'positive' : v >= 0.35 ? 'neutral' : 'negative';
    return `<div class="conf-bar-wrap" title="${pct}%">
      <div class="conf-bar" style="width:${pct}%"></div>
      <span class="${cls}">${pct}%</span>
    </div>`;
  }

  function stage_badge(stage) {
    const map = {
      active:      ['badge-buy',   'ACTIVE'],
      candidate:   ['badge-warn',  'CANDIDATE'],
      observation: ['badge-info',  'OBSERVE'],
      rejected:    ['badge-error', 'REJECTED'],
    };
    const [cls, label] = map[stage] || ['badge-info', stage || '?'];
    return `<span class="badge ${cls}">${label}</span>`;
  }

  function ts_short(v) {
    if (!v) return '—';
    return String(v).replace('T', ' ').slice(0, 16);
  }

  function quality_icon(q) {
    if (q == null) return '—';
    const n = parseFloat(q);
    if (n >= 0.75) return `<span class="positive">✦ ${n.toFixed(2)}</span>`;
    if (n >= 0.5)  return `<span class="neutral">◆ ${n.toFixed(2)}</span>`;
    return `<span class="negative">◇ ${n.toFixed(2)}</span>`;
  }

  function pnl_cell(v) {
    if (v == null) return '—';
    const n = parseFloat(v);
    const cls = n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral';
    return `<span class="${cls}">${n >= 0 ? '+' : ''}${QFFmt.money(n)}</span>`;
  }

  // ─── Render: Overview ────────────────────────────────────────────────────────
  function renderOverview(data) {
    const strats = data.strategies || [];
    const hyps   = data.hypotheses  || {};
    const dq     = data.decision_quality || {};

    // Status badge
    const badge = document.getElementById('learningStatusBadge');
    if (badge) {
      if (data.learning_active) {
        badge.className = 'badge badge-buy';
        badge.textContent = 'LIVE';
      } else {
        badge.className = 'badge badge-warn';
        badge.textContent = 'STANDBY';
      }
    }

    const avgConf = strats.length
      ? strats.reduce((s, r) => s + parseFloat(r.confidence || 0), 0) / strats.length
      : null;

    const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setTxt('lrnStrategies', strats.length || '0');
    setTxt('lrnAvgConf',    avgConf != null ? (avgConf * 100).toFixed(1) + '%' : '—');
    setTxt('lrnHypActive',  hyps.active  ?? '0');
    setTxt('lrnEvaluated',  dq.evaluated ?? '—');
    setTxt('lrnAvgQuality', dq.avg != null ? dq.avg.toFixed(3) : '—');
    setTxt('lrnTotalTrades', data.trades_total ?? '—');
  }

  // ─── Render: Strategies table ────────────────────────────────────────────────
  function renderStrategies(rows) {
    const tbody = document.getElementById('lrnStratBody');
    const badge = document.getElementById('lrnStratBadge');
    if (!tbody) return;

    if (badge) { badge.className = 'badge badge-info'; badge.textContent = `${rows.length} strategies`; }

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Нет данных — стратегии появятся после первых сделок</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const conf = parseFloat(r.confidence || 0);
      const wr   = r.win_rate != null ? (parseFloat(r.win_rate) * 100).toFixed(1) + '%' : '—';
      const pf   = r.profit_factor != null ? parseFloat(r.profit_factor).toFixed(2) : '—';
      const exp  = r.expectancy != null ? parseFloat(r.expectancy).toFixed(3) + ' R' : '—';
      const upd  = r.last_updated ? ts_short(r.last_updated) : '—';
      const regime = r.best_regime || '—';
      return `<tr>
        <td><code class="ticker-chip">${esc(r.strategy_id)}</code></td>
        <td class="num">${conf_bar(conf)}</td>
        <td class="num">${wr}</td>
        <td class="num">${QFFmt.int(r.total_trades)}</td>
        <td class="num">${pf}</td>
        <td class="num">${exp}</td>
        <td><span class="badge badge-info">${esc(regime)}</span></td>
        <td class="muted">${upd}</td>
      </tr>`;
    }).join('');
  }

  // ─── Render: Hypotheses grid ─────────────────────────────────────────────────
  function renderHypotheses(rows) {
    const grid = document.getElementById('lrnHypGrid');
    if (!grid) return;

    if (!rows.length) {
      grid.innerHTML = '<div class="table-empty">Гипотез пока нет — они появятся после накопления статистики</div>';
      return;
    }

    grid.innerHTML = rows.map(h => {
      const wr  = h.win_rate != null ? (parseFloat(h.win_rate) * 100).toFixed(1) + '%' : '—';
      const n   = h.sample_size ?? '?';
      const desc = String(h.description || '').slice(0, 140);
      const hyp_id = String(h.hypothesis_id || '').slice(0, 8);
      const when = h.promoted_at ? `promoted ${ts_short(h.promoted_at)}` :
                   h.rejected_at ? `rejected ${ts_short(h.rejected_at)}` :
                   `observed ${ts_short(h.created_at)}`;
      return `<div class="hyp-card hyp-${esc(h.stage)}">
        <div class="hyp-header">
          ${stage_badge(h.stage)}
          <code class="hyp-id">#${esc(hyp_id)}</code>
          <span class="muted hyp-strat">${esc(h.strategy_id || '')}</span>
        </div>
        <p class="hyp-desc">${esc(desc)}${desc.length >= 140 ? '…' : ''}</p>
        <div class="hyp-stats">
          <span>WR: <strong>${wr}</strong></span>
          <span>n = <strong>${n}</strong></span>
          <span class="muted">${esc(when)}</span>
        </div>
        ${h.rejection_reason ? `<div class="hyp-reject-reason">${esc(h.rejection_reason)}</div>` : ''}
      </div>`;
    }).join('');
  }

  // ─── Render: Decision quality list ───────────────────────────────────────────
  function renderDecisions(rows) {
    const el = document.getElementById('lrnDecisionList');
    if (!el) return;

    if (!rows.length) {
      el.innerHTML = '<div class="table-empty">Нет оценённых сделок</div>';
      return;
    }

    el.innerHTML = `<div class="decision-stream">${rows.slice(0, 25).map(r => {
      const dir = (r.direction || '').toLowerCase();
      const isLong = dir === 'buy' || dir === 'long';
      return `<div class="decision-row">
        <div class="decision-row-left">
          <span class="badge ${isLong ? 'badge-long' : 'badge-short'}">${isLong ? 'L' : 'S'}</span>
          <span class="ticker-chip">${esc(r.ticker)}</span>
          <span class="muted">${ts_short(r.closed_at)}</span>
        </div>
        <div class="decision-row-mid">
          <span title="Decision quality">${quality_icon(r.decision_quality)}</span>
        </div>
        <div class="decision-row-right">
          ${pnl_cell(r.pnl)}
        </div>
        ${r.entry_reason ? `<div class="decision-reason">${esc(String(r.entry_reason).slice(0, 80))}</div>` : ''}
      </div>`;
    }).join('')}</div>`;
  }

  // ─── Render: Skipped signals ─────────────────────────────────────────────────
  function renderSkipped(data) {
    const el = document.getElementById('lrnSkippedList');
    if (!el) return;

    const rows = data.skipped_signals || [];
    if (!rows.length) {
      el.innerHTML = '<div class="table-empty">Нет отклонённых сигналов</div>';
      return;
    }

    const reason_labels = {
      structural_downtrend: 'Структурный даунтренд',
      low_confidence: 'Низкий confidence',
      learning_blocked: 'Обучение заблокировало',
    };

    el.innerHTML = `<div class="skipped-stream">${rows.slice(0, 20).map(r => {
      const reason_label = reason_labels[r.skip_reason] || r.skip_reason || '?';
      return `<div class="skipped-row">
        <div class="skipped-row-top">
          <span class="ticker-chip">${esc(r.ticker || '?')}</span>
          <span class="badge badge-error">${esc(reason_label)}</span>
          <span class="muted">${ts_short(r.created_at)}</span>
        </div>
        <div class="skipped-strat muted">${esc(r.strategy_id || '')}</div>
      </div>`;
    }).join('')}</div>`;
  }

  // ─── API calls ───────────────────────────────────────────────────────────────
  async function loadAll() {
    try {
      const [overview, strategies, decisions, activity] = await Promise.all([
        fetchJSON('/api/platform/learning/overview'),
        fetchJSON('/api/platform/learning/strategies'),
        fetchJSON('/api/platform/learning/decisions?limit=30'),
        fetchJSON('/api/platform/learning/activity'),
      ]);
      renderOverview(overview);
      renderStrategies(strategies);
      renderDecisions(decisions);
      renderSkipped(activity);
    } catch (err) {
      console.warn('[LearningView] load error:', err);
    }
  }

  async function loadHypotheses() {
    try {
      const url = _hyp_stage_filter
        ? `/api/platform/learning/hypotheses?stage=${encodeURIComponent(_hyp_stage_filter)}`
        : '/api/platform/learning/hypotheses';
      const rows = await fetchJSON(url);
      renderHypotheses(rows);
    } catch (err) {
      console.warn('[LearningView] hypotheses error:', err);
    }
  }

  async function runLearningCycle() {
    try {
      const result = await fetchJSON('/api/platform/learning/run_cycle', { method: 'POST' });
      const msg = result.ok ? (result.message || 'Cycle queued') : (result.error || 'Error');
      window.QFToast?.show(msg, result.ok ? 'success' : 'error');
    } catch (err) {
      window.QFToast?.show('Failed to trigger cycle', 'error');
    }
  }

  // ─── Init ────────────────────────────────────────────────────────────────────
  function initView() {
    // Hypothesis stage filter buttons
    document.querySelectorAll('.lrn-hyp-filter').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.lrn-hyp-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _hyp_stage_filter = btn.dataset.stage || '';
        loadHypotheses();
      });
    });

    // Run cycle button
    const runBtn = document.getElementById('btnRunCycle');
    if (runBtn) runBtn.addEventListener('click', runLearningCycle);

    // Full load
    loadAll();
    loadHypotheses();
  }

  // Auto-refresh while view is active
  function startAutoRefresh() {
    stopAutoRefresh();
    _refresh_timer = setInterval(() => {
      if (currentView === 'learning') {
        loadAll();
        loadHypotheses();
      }
    }, REFRESH_INTERVAL);
  }

  function stopAutoRefresh() {
    if (_refresh_timer) { clearInterval(_refresh_timer); _refresh_timer = null; }
  }

  // ─── Register view handler ───────────────────────────────────────────────────
  function _bootstrap() {
    if (typeof viewHandlers !== 'undefined') {
      viewHandlers['learning'] = () => {
        loadAll();
        loadHypotheses();
        startAutoRefresh();
      };
    }

    if (typeof PAGE_TITLES !== 'undefined') {
      PAGE_TITLES['learning'] = ['Learning', 'AI · Sandbox · Intelligence'];
    }

    initView();

    document.addEventListener('qf:sse', e => {
      const { type } = e.detail || {};
      if (
        typeof currentView !== 'undefined' &&
        currentView === 'learning' &&
        ['paper_position_closed', 'paper_trade_executed', 'portfolio_updated'].includes(type)
      ) {
        setTimeout(loadAll, 1500);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _bootstrap);
  } else {
    _bootstrap();
  }

  // ─── CSS injected inline (scoped to learning view) ───────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    /* Confidence bar */
    .conf-bar-wrap { display:flex; align-items:center; gap:8px; min-width:120px; }
    .conf-bar { height:4px; border-radius:2px; background:var(--accent); opacity:0.8; transition:width 0.4s ease; }

    /* Hypothesis grid */
    .learning-hyp-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 12px;
      padding: 16px;
    }
    .hyp-card {
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: border-color 0.2s;
    }
    .hyp-card.hyp-active   { border-color: var(--positive); }
    .hyp-card.hyp-rejected { border-color: var(--negative); opacity: 0.7; }
    .hyp-card.hyp-candidate{ border-color: var(--warning); }
    .hyp-header { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .hyp-id { font-size:11px; color:var(--text-muted); }
    .hyp-strat { font-size:11px; }
    .hyp-desc { font-size:12px; color:var(--text-secondary); line-height:1.5; margin:0; }
    .hyp-stats { display:flex; gap:12px; font-size:11px; flex-wrap:wrap; }
    .hyp-reject-reason { font-size:11px; color:var(--negative); padding:4px 8px; background:rgba(246,70,93,0.1); border-radius:4px; }

    /* Decision stream */
    .decision-stream { padding:8px; display:flex; flex-direction:column; gap:4px; max-height:380px; overflow-y:auto; }
    .decision-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      grid-template-rows: auto auto;
      gap: 2px 8px;
      padding: 8px 12px;
      background: var(--surface-2);
      border-radius: 6px;
      border: 1px solid var(--border);
      font-size: 12px;
    }
    .decision-row-left { display:flex; align-items:center; gap:6px; }
    .decision-row-mid, .decision-row-right { display:flex; align-items:center; }
    .decision-reason { grid-column: 1/-1; font-size:11px; color:var(--text-muted); padding-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

    /* Skipped stream */
    .skipped-stream { padding:8px; display:flex; flex-direction:column; gap:4px; max-height:380px; overflow-y:auto; }
    .skipped-row { padding:8px 12px; background:var(--surface-2); border-radius:6px; border:1px solid var(--border); }
    .skipped-row-top { display:flex; align-items:center; gap:6px; flex-wrap:wrap; font-size:12px; }
    .skipped-strat { font-size:11px; margin-top:2px; }

    /* Learning decision list */
    .learning-decision-list, .learning-skipped-list { min-height:120px; }

    /* Ticker chip */
    .ticker-chip { font-family: var(--font-mono, monospace); font-size:12px; font-weight:600; padding:2px 6px; background:rgba(247,147,26,0.12); border-radius:4px; color:var(--accent); }
  `;
  document.head.appendChild(style);

})();
