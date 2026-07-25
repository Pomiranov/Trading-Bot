/* QuantFlow Platform — Event-driven orchestration */

(function initPlatform() {
  /* ── Store → View bindings ── */
  QFStore.on('sync:complete', () => QFRender.refreshCurrentView());
  QFStore.on('positions:updated', () => {
    if (currentView === 'dashboard' || currentView === 'portfolio') QFRender.refreshCurrentView();
  });
  QFStore.on('signals:updated', () => {
    if (currentView === 'signals' || currentView === 'dashboard') QFRender.refreshCurrentView();
  });
  QFStore.on('operations:updated', () => {
    if (currentView === 'portfolio') QFRender.portfolio(QFStore.get());
  });

  /* ── View handlers ── */
  const _origPortfolio = viewHandlers.portfolio;
  viewHandlers.portfolio = async function () {
    await QFSync.fullSync(true);
    QFRender.portfolio(QFStore.get());
    await _origPortfolio?.();
  };

  viewHandlers.signals = async function () {
    await QFSync.fullSync(true);
    QFRender.signals(QFStore.get());
  };

  viewHandlers.dashboard = async function () {
    await refreshDashboard();
  };

  viewHandlers.backtest = loadBacktestHistory;

  viewHandlers.miniapp = function () {
    window.MiniAppBridge?.init?.({ tab: 'game' });
  };

  /* ── Dashboard refresh ── */
  async function refreshDashboard() {
    if (currentView !== 'dashboard') return;
    const btn = document.getElementById('topbarRefreshBtn');
    btn?.classList.add('spinning');
    await QFSync.fullSync(true);
    try {
      const log = await QFApi.log();
      const list = document.getElementById('logList');
      if (list) {
        list.innerHTML = log.length
          ? log.map(e => `<div class="log-entry"><span class="log-ts">${esc(e.ts)}</span>${QFUI.logBadge(e.level)}<span class="log-msg">${esc(e.message)}</span></div>`).join('')
          : '<div class="empty">Лог пуст</div>';
      }
    } catch (_) {}
    QFRender.dashboard(QFStore.get());
    btn?.classList.remove('spinning');
  }

  window.refreshDashboard = refreshDashboard;
  window.loadPlatformOverview = () => QFRender.dashboard(QFStore.get());

  dashboardRefresh = refreshDashboard;

  /* ── Signals actions ── */
  async function generateSignals() {
    const btn = document.getElementById('generateSignalsBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Генерация…'; }
    try {
      const data = await QFApi.generateSignals();
      QFUI.toast(`Сгенерировано ${data.length} сигналов`, 'success');
      await QFSync.fullSync(true);
      QFRender.signals(QFStore.get());
    } catch (err) {
      QFUI.toast(err.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Сгенерировать'; }
    }
  }

  async function executeSignal(id) {
    const ok = await QFUI.confirm('Открыть paper-сделку по этому сигналу?');
    if (!ok) return;
    try {
      const res = await QFApi.executeSignal(id);
      if (res.ok) {
        QFUI.toast(`Позиция #${res.position_id} открыта`, 'success');
        await QFSync.fullSync(true);
        QFRender.refreshCurrentView();
      } else QFUI.toast(res.error || 'Ошибка', 'error');
    } catch (err) {
      QFUI.toast(err.message, 'error');
    }
  }

  window.generateSignals = generateSignals;
  window.executeSignal = executeSignal;

  /* ── Backtest ── */
  async function runPlatformBacktest() {
    const btn = document.getElementById('runBacktestBtn');
    const status = document.getElementById('backtestStatus');
    const resEl = document.getElementById('backtestResults');
    const body = {
      strategy: document.getElementById('btStrategy')?.value || 'rules_engine',
      exchange: document.getElementById('btExchange')?.value || 'moex',
      ticker: document.getElementById('btTicker')?.value || 'SBER',
      period_start: document.getElementById('btPeriodStart')?.value || null,
      period_end: document.getElementById('btPeriodEnd')?.value || null,
      initial_capital: parseFloat(document.getElementById('btCapital')?.value || 1000000),
      risk_pct: parseFloat(document.getElementById('btRisk')?.value || 0.05),
      commission_pct: parseFloat(document.getElementById('btCommission')?.value || 0.0003),
      slippage_pct: parseFloat(document.getElementById('btSlippage')?.value || 0.0001),
      leverage: parseFloat(document.getElementById('btLeverage')?.value || 1),
    };

    btn.disabled = true;
    btn.textContent = 'Вычисление…';
    status.innerHTML = QFUI.empty('⚙️', 'Запуск…', 'Анализ исторических данных');

    try {
      const r = await QFApi.backtestRun(body);
      status.innerHTML = QFUI.empty('✅', 'Завершён', `${r.ticker} · ${r.total_trades} сделок · WR ${r.win_rate}%`);
      resEl.style.display = 'block';
      QFUI.toast(`Backtest #${r.run_id} завершён`, 'success');
      document.getElementById('backtestMeta').textContent = `Run #${r.run_id} · ${r.strategy}`;

      const _fmt2 = (v, d = 2) => v != null ? Number(v).toFixed(d) : '—';
      const metrics = [
        ['Баланс', QFFmt.money(r.final_balance)],
        ['PnL', (r.total_pnl >= 0 ? '+' : '') + QFFmt.money(r.total_pnl)],
        ['Просадка', r.max_drawdown != null ? '-' + _fmt2(Math.abs(r.max_drawdown)) + '%' : '—'],
        ['Win Rate', r.win_rate != null ? _fmt2(r.win_rate, 1) + '%' : '—'],
        ['Profit Factor', r.profit_factor != null ? _fmt2(r.profit_factor) : '—'],
        ['Sharpe', r.sharpe_ratio != null ? _fmt2(r.sharpe_ratio) : '—'],
        ['Sortino', r.sortino_ratio != null ? _fmt2(r.sortino_ratio) : '—'],
        ['Calmar', r.calmar_ratio != null ? _fmt2(r.calmar_ratio) : '—'],
        ['Сделок', r.total_trades ?? '—'],
        ['Макс.+', QFFmt.money(r.max_profit)],
        ['Макс.−', QFFmt.money(r.max_loss)],
        ['Ср.+', QFFmt.money(r.avg_profit)],
        ['Ср.−', QFFmt.money(r.avg_loss)],
        ['Hold', r.avg_hold_bars != null ? r.avg_hold_bars + ' bars' : '—'],
      ];
      QFRender.backtestMetrics(metrics);

      document.getElementById('backtestBody').innerHTML = (r.trades || []).map(t => `
        <tr><td class="ticker-cell">${esc(t.ticker)}</td><td class="mono num">${QFFmt.num(t.entry_price)}</td>
        <td class="mono num">${QFFmt.num(t.exit_price)}</td>
        <td class="mono num ${QFFmt.colorClass(t.pnl)}">${t.pnl >= 0 ? '+' : ''}${QFFmt.money(t.pnl)}</td>
        <td class="mono num">${t.pnl_pct}%</td><td>${esc(t.status)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Нет сделок</td></tr>';

      QFChart.line('backtestChart', (r.equity_curve || []).map(e => ({ time: e.ts, value: e.equity })));
      QFChart.drawdown('backtestDrawdownChart', r.drawdown_curve || []);
      QFChart.heatmap('backtestHeatmapChart', r.heatmap || []);
      QFChart.calendar('backtestCalendarChart', r.return_calendar || []);

      document.getElementById('exportBacktestBtn').onclick = () => {
        window.open(`/api/platform/backtest/runs/${r.run_id}/export`, '_blank');
      };
      setTimeout(() => QFChart.resizeAll(), 100);
    } catch (err) {
      status.innerHTML = QFUI.empty('❌', 'Ошибка', err.message);
      QFUI.toast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Запустить';
    }
  }

  async function loadBacktestHistory() {
    try {
      const runs = await QFApi.backtestRuns();
      const el = document.getElementById('backtestHistory');
      if (!el) return;
      el.innerHTML = runs.length
        ? runs.map(r => `<div class="recent-item recent-click" data-run-id="${Number(r.id)}" style="cursor:pointer">
            <span>#${Number(r.id)} ${esc(r.ticker)} · ${esc(r.strategy || 'rules')}</span>
            <span class="ts-cell">${esc(String(r.created_at).slice(0, 16))}</span></div>`).join('')
        : '<div class="empty">История пуста</div>';

      el.querySelectorAll('[data-run-id]').forEach(row => {
        row.addEventListener('click', () => loadBacktestRun(Number(row.dataset.runId)));
      });

      if (runs.length) await loadBacktestRun(runs[0].id);
    } catch (_) {}
  }

  async function loadBacktestRun(runId) {
    try {
      const raw = await QFApi.request(`/api/platform/backtest/runs/${runId}/export`);
      const nested = typeof raw.results === 'string' ? JSON.parse(raw.results) : (raw.results || {});
      const r = { ...nested, strategy: nested.strategy || raw.strategy, ticker: nested.ticker || raw.ticker, run_id: runId };
      const resEl = document.getElementById('backtestResults');
      if (!resEl) return;
      resEl.style.display = 'block';
      document.getElementById('backtestStatus').innerHTML = QFUI.empty('📂', `Run #${runId}`, `${r.ticker} · ${r.total_trades} сделок`);
      document.getElementById('backtestMeta').textContent = `Run #${runId} · ${r.strategy}`;

      const fmtMetric = (v, decimals = 2) => v != null ? Number(v).toFixed(decimals) : '—';
      const metrics = [
        ['Баланс', QFFmt.money(r.final_balance)],
        ['PnL', (r.total_pnl >= 0 ? '+' : '') + QFFmt.money(r.total_pnl)],
        ['Просадка', r.max_drawdown != null ? '-' + fmtMetric(Math.abs(r.max_drawdown)) + '%' : '—'],
        ['Win Rate', r.win_rate != null ? fmtMetric(r.win_rate, 1) + '%' : '—'],
        ['Profit Factor', r.profit_factor != null ? fmtMetric(r.profit_factor) : '—'],
        ['Sharpe', r.sharpe_ratio != null ? fmtMetric(r.sharpe_ratio) : '—'],
        ['Sortino', r.sortino_ratio != null ? fmtMetric(r.sortino_ratio) : '—'],
        ['Calmar', r.calmar_ratio != null ? fmtMetric(r.calmar_ratio) : '—'],
        ['Сделок', r.total_trades ?? '—'],
      ];
      QFRender.backtestMetrics(metrics);

      document.getElementById('backtestBody').innerHTML = (r.trades || []).slice(0, 50).map(t => {
        const pnlPct = t.pnl_pct != null ? Number(t.pnl_pct).toFixed(2) : '—';
        return `<tr><td class="ticker-cell">${esc(t.ticker)}</td><td class="mono num">${QFFmt.num(t.entry_price)}</td>
        <td class="mono num">${QFFmt.num(t.exit_price)}</td>
        <td class="mono num ${QFFmt.colorClass(t.pnl)}">${t.pnl >= 0 ? '+' : ''}${QFFmt.money(t.pnl)}</td>
        <td class="mono num">${pnlPct}%</td><td>${esc(t.status)}</td></tr>`;
      }).join('') || '<tr><td colspan="6" class="empty">Нет сделок</td></tr>';

      QFChart.line('backtestChart', (r.equity_curve || []).map(e => ({ time: e.ts, value: e.equity })));
      QFChart.drawdown('backtestDrawdownChart', r.drawdown_curve || []);
      QFChart.heatmap('backtestHeatmapChart', r.heatmap || []);
      QFChart.calendar('backtestCalendarChart', r.return_calendar || []);
      document.getElementById('exportBacktestBtn').onclick = () => window.open(`/api/platform/backtest/runs/${runId}/export`, '_blank');
      setTimeout(() => QFChart.resizeAll(), 100);
    } catch (err) {
      console.warn('[Backtest load]', err);
    }
  }

  /* ── Filter listeners ── */
  ['filterExchange', 'filterAssetClass', 'filterStrategy', 'filterDirection', 'filterAsset', 'filterDateFrom'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => QFRender.signals(QFStore.get()));
    document.getElementById(id)?.addEventListener('input', () => QFRender.signals(QFStore.get()));
  });
  document.getElementById('assetSearch')?.addEventListener('input', () => QFRender.portfolio(QFStore.get()));

  document.getElementById('generateSignalsBtn')?.addEventListener('click', generateSignals);
  document.getElementById('refreshSignalsBtn')?.addEventListener('click', async () => {
    await QFSync.fullSync(true);
    QFRender.signals(QFStore.get());
  });
  document.getElementById('runBacktestBtn')?.addEventListener('click', runPlatformBacktest);

  /* ── Bootstrap ── */
  QFApi.settings().then(d => { window._maxOpenPositions = d.risk?.max_open_positions || 10; }).catch(() => {});
  QFSync.connect();
  QFSync.fullSync(true).then(() => {
    QFRender.dashboard(QFStore.get());
    if (currentView !== 'dashboard') QFRender.refreshCurrentView();
  });
})();