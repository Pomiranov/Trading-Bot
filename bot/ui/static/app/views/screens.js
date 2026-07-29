/**
 * The remaining eleven screens.
 *
 * Most are the same shape — a filter bar, a metric strip, a table, sometimes a
 * chart — so they share one factory rather than eleven near-copies. That is what
 * makes "every data region implements all ten states" true by construction: the
 * state handling lives in the factory, not in each screen's render function.
 *
 * Filters live in the URL, so a filtered view is linkable and survives a reload.
 */

import { BarChart, Histogram, LineChart, StepChart, UnderwaterChart, seriesSummary } from '../charts.js';
import { append, el, render } from '../dom.js';
import * as fmt from '../format.js';
import { t } from '../i18n.js';
import { DataTable } from '../table.js';
import {
  actionButton, chartPanel, chip, confidenceValue, environmentChip, freshnessMeta,
  metric, metricsGrid, moneyMetric, panel, partialNote, percentMetric, stateFor,
  status, toasts,
} from '../ui.js';

const PERIODS = [
  ['1d', 'сутки'], ['7d', '7 дней'], ['30d', '30 дней'],
  ['90d', '90 дней'], ['1y', 'год'], ['all', 'вся история'],
];

const ENVIRONMENTS = [
  ['sandbox', 'песочница'], ['forward', 'форвард'],
  ['backtest', 'бэктест'], ['live', 'LIVE'],
];

/** A labelled `<select>` that writes its value into the URL. */
function selectFilter({ id, label, options, value, onChange, includeAll = false }) {
  const select = el('select', { className: 'qf-select', attrs: { id } });
  if (includeAll) {
    select.appendChild(el('option', { text: t('common.all'), attrs: { value: '' } }));
  }
  for (const [optionValue, optionLabel] of options) {
    select.appendChild(el('option', {
      text: optionLabel,
      attrs: { value: optionValue, selected: optionValue === value },
    }));
  }
  select.addEventListener('change', () => onChange(select.value));
  return el('div', { className: 'qf-field' }, [
    el('label', { className: 'qf-field-label', text: label, attrs: { for: id } }),
    select,
  ]);
}

function textFilter({ id, label, value, placeholder, onChange }) {
  const input = el('input', {
    className: 'qf-input',
    attrs: { id, type: 'search', value: value || '', placeholder: placeholder || '' },
  });
  let timer = null;
  input.addEventListener('input', () => {
    // Debounced: a filter that fires a request per keystroke is what a
    // five-connection pool cannot absorb.
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => onChange(input.value.trim()), 350);
  });
  return el('div', { className: 'qf-field' }, [
    el('label', { className: 'qf-field-label', text: label, attrs: { for: id } }),
    input,
  ]);
}

/**
 * The generic screen factory.
 *
 * @param config
 *   title, slice, columns(context), rows(data), metrics(data, meta),
 *   filters(context, params, setParam), extras(data, meta), storageKey,
 *   emptyExtra, tableCaption, density
 */
function tableScreen(config) {
  return (context) => {
    const built = panel({ title: config.title, flush: true });
    const filterBar = el('div', { className: 'qf-panel-body qf-toolbar' });
    const metricHost = el('div');
    const tableHost = el('div');
    const extraHost = el('div');

    render(built.body, [filterBar, metricHost, tableHost, extraHost]);

    const table = new DataTable(tableHost, {
      caption: config.tableCaption,
      storageKey: config.storageKey,
      density: config.density || 'compact',
      columns: config.columns(context),
      rowKey: config.rowKey || ((row, index) => row.id ?? index),
      serverSort: Boolean(config.serverSort),
      onSortChange: config.serverSort
        ? (key, desc) => context.setParams({ sort: `${desc ? '-' : ''}${key}` })
        : undefined,
      onSelect: config.onSelect ? (row) => config.onSelect(context, row, extraHost) : undefined,
    });

    const root = el('div', { className: 'qf-view', dataset: { view: config.slice } }, [
      built.root,
      ...(config.after ? config.after(context) : []),
    ]);

    function renderFilters() {
      if (!config.filters) return;
      render(filterBar, config.filters(context, context.params(), (name, value) => {
        context.setParams({ [name]: value });
      }));
    }

    function update(snapshot) {
      built.root.setAttribute('aria-busy',
        snapshot.state === 'refreshing' || snapshot.state === 'loading' ? 'true' : 'false');
      render(built.meta, [
        freshnessMeta(snapshot.meta),
        snapshot.meta && snapshot.meta.n !== undefined
          ? el('span', { text: fmt.sampleSuffix(snapshot.meta.n) })
          : null,
      ]);

      const fallback = stateFor(snapshot, {
        onRetry: () => context.refresh(config.slice),
        skeleton: 5,
        emptyExtra: config.emptyExtra,
      });

      if (fallback) {
        render(metricHost, null);
        render(tableHost, fallback);
        // Rebuild the table on the next successful payload; the host was replaced.
        return;
      }
      if (!snapshot.hasData) return;

      if (config.metrics) {
        render(metricHost, config.metrics(snapshot.data, snapshot.meta));
      }
      if (!tableHost.contains(table.wrap)) {
        tableHost.replaceChildren(table.wrap);
      }
      table.setRows(config.rows(snapshot.data));
      if (config.extras) render(extraHost, config.extras(snapshot.data, snapshot.meta, context));

      const note = partialNote(snapshot.meta && snapshot.meta.missing);
      if (note) append(extraHost, note);
    }

    return {
      root,
      slices: [config.slice],
      mount() {
        renderFilters();
        const offParams = context.onParamsChange(renderFilters);
        const offSlice = context.subscribe(config.slice, update);
        return () => { offParams(); offSlice(); };
      },
      dispose() {
        table.dispose();
      },
    };
  };
}

// ── Positions ────────────────────────────────────────────────────────────────

export const createPositions = tableScreen({
  title: t('nav.positions'),
  slice: 'positions',
  storageKey: 'positions',
  density: 'comfortable',
  tableCaption: 'Открытые позиции с расстоянием до стопа, возрастом котировки и средой исполнения.',
  filters: (context, params, setParam) => [
    selectFilter({
      id: 'positions-env', label: t('common.environment'), options: ENVIRONMENTS,
      value: params.environment || 'sandbox', onChange: (v) => setParam('environment', v),
    }),
  ],
  metrics: (data) => {
    const totals = data.totals || {};
    return metricsGrid([
      moneyMetric({ label: t('risk.exposure'), value: totals.exposure_abs, currency: data.currency, signed: false }),
      percentMetric({ label: `${t('risk.exposure')}, %`, value: totals.exposure_pct, signed: false }),
      moneyMetric({ label: t('positions.unrealized'), value: totals.unrealized_pnl, currency: data.currency }),
      metric({ label: t('risk.stale_marks'), value: fmt.integer(data.stale_quote_count || 0),
        tone: data.stale_quote_count ? 'qf-negative' : undefined }),
    ]);
  },
  rows: (data) => data.positions || [],
  columns: (context) => {
    const canClose = context.session.can('close_position');
    return [
      { key: 'ticker', label: t('positions.ticker'), sortable: true,
        render: (row) => el('span', { className: 'qf-mono', text: row.ticker }) },
      { key: 'direction', label: t('positions.direction'),
        render: (row) => chip(row.direction === 'short' ? 'SHORT' : 'LONG',
          { tone: row.direction === 'short' ? 'negative' : 'positive' }) },
      { key: 'quantity', label: t('positions.quantity'), numeric: true, sortable: true,
        render: (row) => fmt.quantity(row.quantity, t('unit.pieces')) },
      { key: 'entry_price', label: t('positions.entry'), numeric: true,
        render: (row) => fmt.price(row.entry_price) },
      { key: 'mark_price', label: t('positions.mark'), numeric: true,
        stale: (row) => row.mark_is_stale === true,
        title: (row) => (row.mark_as_of ? fmt.absoluteTime(row.mark_as_of) : t('positions.no_quote')),
        render: (row) => (fmt.isNumber(row.mark_price)
          ? fmt.price(row.mark_price)
          : el('span', { className: 'qf-unknown-value', text: t('positions.no_quote') })) },
      { key: 'mark_age_seconds', label: t('positions.mark_age'), numeric: true, sortable: true,
        render: (row) => (fmt.isNumber(row.mark_age_seconds)
          ? el('span', { className: row.mark_is_stale ? 'qf-stale' : '', text: fmt.age(row.mark_age_seconds) })
          : fmt.NO_DATA) },
      { key: 'stop_loss', label: 'Стоп', numeric: true,
        render: (row) => (fmt.isNumber(row.stop_loss) ? fmt.price(row.stop_loss)
          : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
      { key: 'distance_to_stop_pct', label: t('positions.distance_to_stop'), numeric: true, sortable: true,
        render: (row) => (fmt.isNumber(row.distance_to_stop_pct)
          ? el('span', { className: fmt.signClass(-Math.abs(row.distance_to_stop_pct)), text: fmt.percent(row.distance_to_stop_pct) })
          : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
      { key: 'unrealized_pnl', label: t('positions.unrealized'), numeric: true, sortable: true,
        render: (row) => (fmt.isNumber(row.unrealized_pnl)
          ? el('span', { className: fmt.signClass(row.unrealized_pnl), text: fmt.money(row.unrealized_pnl, { signed: true }) })
          : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
      { key: 'strategy_id', label: t('positions.strategy'),
        render: (row) => el('span', { className: 'qf-mono qf-truncate', text: row.strategy_id || fmt.NO_DATA, title: row.strategy_id }) },
      { key: 'environment', label: t('positions.environment'),
        render: (row) => environmentChip(row.environment) },
      // The close action existed in the API and was wired to no control at all.
      // Here it is present, and when it is unavailable it says why.
      { key: 'actions', label: '', align: 'end',
        render: (row) => actionButton({
          label: t('positions.close'),
          danger: true,
          permitted: canClose,
          reason: context.session.denialReason('close_position'),
          onClick: () => context.closePosition(row),
        }) },
    ];
  },
});

// ── Trades ───────────────────────────────────────────────────────────────────

export const createTrades = tableScreen({
  title: t('trades.title'),
  slice: 'trades',
  storageKey: 'trades',
  density: 'compact',
  serverSort: true,
  tableCaption: 'Закрытые сделки: цены входа и выхода, PnL в деньгах и процентах, комиссия, длительность, причина закрытия и среда.',
  emptyExtra: 'Проверьте период и фильтры — сделки могли закрыться раньше.',
  filters: (context, params, setParam) => [
    selectFilter({ id: 'trades-period', label: t('common.period'), options: PERIODS,
      value: params.period || '30d', onChange: (v) => setParam('period', v) }),
    selectFilter({ id: 'trades-env', label: t('common.environment'), options: ENVIRONMENTS,
      value: params.environment || 'sandbox', onChange: (v) => setParam('environment', v) }),
    selectFilter({ id: 'trades-result', label: t('trades.result'), includeAll: true,
      options: [['win', t('trades.result.win')], ['loss', t('trades.result.loss')], ['flat', t('trades.result.flat')]],
      value: params.result || '', onChange: (v) => setParam('result', v) }),
    selectFilter({ id: 'trades-direction', label: t('positions.direction'), includeAll: true,
      options: [['long', 'LONG'], ['short', 'SHORT']],
      value: params.direction || '', onChange: (v) => setParam('direction', v) }),
    textFilter({ id: 'trades-ticker', label: t('positions.ticker'), value: params.ticker,
      placeholder: 'SBER', onChange: (v) => setParam('ticker', v) }),
  ],
  metrics: (data) => metricsGrid([
    metric({ label: t('trades.showing'),
      value: `${fmt.integer(data.returned)} ${t('trades.of')} ${fmt.integer(data.total)}`,
      sub: data.period_label }),
  ]),
  rows: (data) => data.trades || [],
  columns: () => [
    { key: 'closed_at', label: t('trades.closed_at'), sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: fmt.smartTime(row.closed_at),
        title: row.closed_at ? fmt.absoluteTime(row.closed_at) : undefined }) },
    { key: 'ticker', label: t('positions.ticker'), sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: row.ticker }) },
    { key: 'direction', label: t('positions.direction'), sortable: true,
      render: (row) => chip(row.direction === 'short' ? 'SHORT' : 'LONG',
        { tone: row.direction === 'short' ? 'negative' : 'positive' }) },
    { key: 'entry_price', label: t('trades.entry'), numeric: true, sortable: true,
      render: (row) => fmt.price(row.entry_price) },
    { key: 'exit_price', label: t('trades.exit'), numeric: true, sortable: true,
      render: (row) => fmt.price(row.exit_price) },
    { key: 'quantity', label: t('positions.quantity'), numeric: true, sortable: true,
      render: (row) => fmt.quantity(row.quantity, t('unit.pieces')) },
    { key: 'pnl', label: t('trades.pnl_money'), numeric: true, sortable: true,
      render: (row) => el('span', { className: fmt.signClass(row.pnl),
        text: fmt.money(row.pnl, { signed: true }) }) },
    { key: 'pnl_pct', label: t('trades.pnl_pct'), numeric: true, sortable: true,
      render: (row) => el('span', { className: fmt.signClass(row.pnl_pct),
        text: fmt.percent(row.pnl_pct) }) },
    // `pnl_r` does not exist on paper_trades. `н/д` rather than 0R, so an absent
    // field is not read as a measured result.
    { key: 'pnl_r', label: t('trades.pnl_r'), numeric: true,
      render: (row) => (fmt.isNumber(row.pnl_r) ? fmt.rMultiple(row.pnl_r)
        : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
    { key: 'commission', label: t('trades.commission'), numeric: true, sortable: true,
      render: (row) => fmt.money(row.commission, { signed: false }) },
    { key: 'duration_seconds', label: t('trades.duration'), numeric: true, sortable: true,
      render: (row) => fmt.duration(row.duration_seconds) },
    { key: 'close_reason', label: t('trades.reason'),
      render: (row) => el('span', { className: 'qf-truncate', text: row.close_reason || fmt.NO_DATA,
        title: row.entry_reason || row.close_reason || undefined }) },
    { key: 'environment', label: t('positions.environment'),
      render: (row) => environmentChip(row.environment) },
  ],
});

// ── Signals ──────────────────────────────────────────────────────────────────

export const createSignals = tableScreen({
  title: t('signals.title'),
  slice: 'signals',
  storageKey: 'signals',
  density: 'compact',
  tableCaption: 'Сигналы и решения шлюза: этап, причина, уверенность с размером выборки, возраст свечи и среда.',
  filters: (context, params, setParam) => [
    selectFilter({ id: 'signals-decision', label: t('signals.decision'), includeAll: true,
      options: [
        ['filled', 'Исполнен'], ['pending', 'Ожидает'],
        ['rejected', 'Отклонён'], ['skipped', 'Пропущен фильтром'],
        ['duplicate', 'Дубликат подавлен'], ['accepted_unfilled', 'Принят, брокер отказал'],
        ['errored', 'Ошибка'], ['unknown', 'Решение не записано'],
      ],
      value: params.decision || '', onChange: (v) => setParam('decision', v) }),
    selectFilter({ id: 'signals-env', label: t('common.environment'), options: ENVIRONMENTS,
      value: params.environment || 'sandbox', onChange: (v) => setParam('environment', v) }),
    textFilter({ id: 'signals-ticker', label: t('positions.ticker'), value: params.ticker,
      placeholder: 'SBER', onChange: (v) => setParam('ticker', v) }),
  ],
  metrics: (data) => {
    const census = data.census || {};
    return metricsGrid(Object.entries(census).slice(0, 6).map(([key, count]) => {
      const label = (data.decisions || []).find((d) => d.value === key);
      return metric({ label: (label && label.label) || key, value: fmt.integer(count) });
    }));
  },
  extras: (data) => (data.gate_recording_note
    ? el('div', { className: 'qf-panel-body' }, [
      el('p', { className: 'qf-state-detail', text: data.gate_recording_note }),
    ])
    : null),
  rows: (data) => data.signals || [],
  rowKey: (row) => `${row.origin}:${row.id}`,
  columns: () => [
    { key: 'occurred_at', label: 'Время', sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: fmt.smartTime(row.occurred_at),
        title: row.occurred_at ? fmt.absoluteTime(row.occurred_at) : undefined }) },
    { key: 'ticker', label: t('positions.ticker'), sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: row.ticker || fmt.NO_DATA }) },
    { key: 'direction', label: t('positions.direction'),
      render: (row) => (row.direction ? chip(row.direction,
        { tone: /SHORT|SELL/i.test(row.direction) ? 'negative' : 'positive' }) : fmt.NO_DATA) },
    { key: 'strategy_id', label: t('positions.strategy'),
      render: (row) => el('span', { className: 'qf-mono qf-truncate', text: row.strategy_id || fmt.NO_DATA,
        title: row.strategy_id }) },
    { key: 'gate_decision', label: t('signals.decision'), sortable: true,
      render: (row) => chip(row.gate_decision_label, { tone: row.gate_tone }) },
    { key: 'gate_stage', label: t('signals.stage'),
      render: (row) => el('span', { className: 'qf-caption', text: row.gate_stage_label }) },
    { key: 'gate_reason', label: t('signals.reason'),
      render: (row) => el('span', {
        className: row.gate_reason_missing ? 'qf-unknown-value qf-truncate' : 'qf-truncate',
        text: row.gate_reason || t('signals.reason_missing'),
        title: row.gate_reason || undefined,
      }) },
    { key: 'confidence', label: t('strategies.confidence'), numeric: true,
      render: (row) => (fmt.isNumber(row.confidence)
        ? confidenceValue(row.confidence, row.sample_size, { mature: row.confidence_is_mature })
        : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
    { key: 'source_candle_age_seconds', label: t('signals.candle_age'), numeric: true,
      render: (row) => (fmt.isNumber(row.source_candle_age_seconds)
        ? el('span', { className: row.source_candle_stale ? 'qf-stale' : '',
          text: fmt.age(row.source_candle_age_seconds),
          title: row.source_candle_at ? fmt.absoluteTime(row.source_candle_at) : undefined })
        : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
    { key: 'environment', label: t('positions.environment'),
      render: (row) => environmentChip(row.environment) },
  ],
});

// ── Strategies ───────────────────────────────────────────────────────────────

export const createStrategies = tableScreen({
  title: t('strategies.title'),
  slice: 'strategies',
  storageKey: 'strategies',
  density: 'comfortable',
  tableCaption: 'Стратегии: состояние, уверенность с размером выборки, доля прибыльных с числителем и знаменателем, profit factor, ожидание, лучший режим и время обновления.',
  emptyExtra: t('state.STRATEGY_NEVER_RAN'),
  metrics: (data) => metricsGrid([
    metric({ label: 'Стратегий', value: fmt.integer(data.count) }),
    metric({ label: 'В рейтинге', value: fmt.integer(data.ranked_count),
      sub: `порог ${fmt.integer(30)} сделок` }),
    metric({ label: t('strategies.immature'), value: fmt.integer(data.immature_count),
      tone: data.immature_count ? 'qf-unknown-value' : undefined,
      sub: t('strategies.excluded_from_ranking') }),
  ]),
  extras: () => el('div', { className: 'qf-panel-body' }, [
    el('p', { className: 'qf-state-detail', text: t('strategies.confidence_note') }),
  ]),
  rows: (data) => data.strategies || [],
  rowKey: (row) => row.strategy_id,
  columns: () => [
    { key: 'rank', label: '#', numeric: true,
      render: (row) => (row.rank ? fmt.integer(row.rank)
        : el('span', { className: 'qf-unknown-value', text: '—' })) },
    { key: 'strategy_id', label: 'Стратегия',
      render: (row) => el('div', {}, [
        el('div', { text: row.name }),
        el('div', { className: 'qf-mono qf-caption qf-truncate', text: row.strategy_id, title: row.strategy_id }),
      ]) },
    { key: 'state', label: t('strategies.state'),
      render: (row) => status({
        state: row.state === 'active' ? 'healthy' : row.state === 'candidate' ? 'unknown' : 'paused',
        label: row.state_label,
        shape: row.state === 'active' ? 'dot-filled' : row.state === 'candidate' ? 'ring-dashed' : 'square',
        title: [row.state_reason, row.state_basis].filter(Boolean).join(' · '),
      }) },
    { key: 'confidence', label: t('strategies.confidence'), numeric: true, sortable: true,
      render: (row) => confidenceValue(row.confidence, row.sample_size,
        { mature: row.confidence_is_mature }) },
    // Win rate always with its numerator and denominator.
    { key: 'win_rate_pct', label: t('strategies.win_rate'), numeric: true, sortable: true,
      render: (row) => el('span', { text: fmt.winRate(row.win_rate_pct, row.wins, row.win_rate_n) }) },
    { key: 'profit_factor', label: t('strategies.profit_factor'), numeric: true, sortable: true,
      render: (row) => (row.confidence_is_mature ? fmt.number(row.profit_factor, 2)
        : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
    { key: 'expectancy', label: t('strategies.expectancy'), numeric: true, sortable: true,
      render: (row) => (fmt.isNumber(row.expectancy) ? fmt.number(row.expectancy, 3) : fmt.NO_DATA) },
    { key: 'best_regime', label: t('strategies.best_regime'),
      render: (row) => row.best_regime || fmt.NO_DATA },
    { key: 'environments', label: t('common.environment'),
      render: (row) => el('span', { className: 'qf-toolbar' },
        (row.environments || []).map((env) => environmentChip(env))) },
    { key: 'updated_at', label: t('strategies.updated'), numeric: true, sortable: true,
      render: (row) => el('span', {
        className: row.updated_age_seconds > 86400 ? 'qf-stale' : 'qf-mono',
        text: fmt.age(row.updated_age_seconds),
        title: row.updated_at ? fmt.absoluteTime(row.updated_at) : undefined,
      }) },
  ],
});

// ── Risk ─────────────────────────────────────────────────────────────────────

export function createRisk(context) {
  const summary = panel({ title: t('nav.risk'), flush: true });
  const breaches = panel({ title: t('risk.breaches'), flush: true });
  const history = panel({ title: 'История риск-событий', flush: true });

  const historyTable = new DataTable(history.body, {
    caption: 'Риск-события: время, инструмент, стратегия, этап шлюза и причина отказа.',
    storageKey: 'risk-events',
    density: 'compact',
    columns: [
      { key: 'occurred_at', label: 'Время', sortable: true,
        render: (row) => el('span', { className: 'qf-mono', text: fmt.smartTime(row.occurred_at) }) },
      { key: 'ticker', label: t('positions.ticker'),
        render: (row) => el('span', { className: 'qf-mono', text: row.ticker || fmt.NO_DATA }) },
      { key: 'strategy_id', label: t('positions.strategy'),
        render: (row) => el('span', { className: 'qf-mono qf-truncate', text: row.strategy_id || fmt.NO_DATA }) },
      { key: 'code', label: 'Код', render: (row) => el('span', { className: 'qf-mono', text: row.code || fmt.NO_DATA }) },
      { key: 'reason', label: t('signals.reason'),
        render: (row) => el('span', { className: 'qf-truncate', text: row.reason || fmt.NO_DATA, title: row.reason }) },
      { key: 'environment', label: t('common.environment'),
        render: (row) => environmentChip(row.environment) },
    ],
    rowKey: (row, index) => `${row.occurred_at}:${index}`,
  });

  const root = el('div', { className: 'qf-view', dataset: { view: 'risk' } },
    [summary.root, breaches.root, history.root]);

  function updateRisk(snapshot) {
    summary.root.setAttribute('aria-busy', snapshot.state === 'refreshing' ? 'true' : 'false');
    render(summary.meta, [freshnessMeta(snapshot.meta)]);

    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('risk'), skeleton: 4 });
    if (fallback) { render(summary.body, fallback); return; }
    if (!snapshot.hasData) return;

    const data = snapshot.data;
    const currency = data.currency || 'RUB';
    const drawdown = data.drawdown || {};
    const risked = data.capital_at_risk || {};
    const daily = data.daily || {};
    const sizing = data.sizing || {};

    render(summary.body, metricsGrid([
      moneyMetric({ label: 'Капитал', value: data.equity, currency, signed: false, large: true }),
      moneyMetric({ label: t('risk.exposure'), value: data.exposure.abs, currency, signed: false }),
      percentMetric({ label: `${t('risk.exposure')}, %`, value: data.exposure.pct, signed: false }),
      moneyMetric({ label: t('risk.capital_at_risk'), value: risked.abs, currency, signed: false }),
      percentMetric({ label: `${t('risk.capital_at_risk')}, %`, value: risked.pct, signed: false }),
      metric({ label: 'Позиций без стопа', value: fmt.integer(risked.positions_without_stop || 0),
        tone: risked.positions_without_stop ? 'qf-negative' : undefined,
        sub: risked.positions_without_stop ? 'риск занижен' : undefined }),
      percentMetric({ label: t('risk.drawdown_max'), value: drawdown.max_pct,
        n: drawdown.n, window: drawdown.window_label }),
      moneyMetric({ label: `${t('risk.drawdown_max')}, ${fmt.currencySymbol(currency)}`,
        value: drawdown.max_abs, currency, n: drawdown.n }),
      percentMetric({ label: t('risk.drawdown_current'), value: drawdown.current_pct, n: drawdown.n }),
      metric({ label: t('risk.positions'),
        value: data.positions.limit_configured
          ? `${fmt.integer(data.positions.open)} / ${fmt.integer(data.positions.limit)}`
          : fmt.integer(data.positions.open),
        sub: data.positions.limit_configured ? undefined : t('risk.not_configured') }),
      daily.limit_pct && daily.limit_pct.configured
        ? metric({ label: t('risk.daily_limit'),
          value: fmt.percent(-Math.abs(daily.limit_pct.value)),
          sub: `${fmt.money(daily.limit_abs_derived, { currency })} ${fmt.MIDDOT} ${t('risk.derived')}` })
        : metric({ label: t('risk.daily_limit'), value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
      moneyMetric({ label: `PnL сегодня`, value: daily.pnl, n: daily.n, currency }),
      percentMetric({ label: t('risk.concentration'), value: data.concentration_pct, signed: false }),
      sizing.max_position_pct && sizing.max_position_pct.configured
        ? percentMetric({ label: 'Макс. размер позиции', value: sizing.max_position_pct.value, signed: false })
        : metric({ label: 'Макс. размер позиции', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
      sizing.atr_stop_multiplier && sizing.atr_stop_multiplier.configured
        ? metric({ label: 'ATR-множитель стопа', value: fmt.number(sizing.atr_stop_multiplier.value, 1) })
        : metric({ label: 'ATR-множитель стопа', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
    ]));

    const list = data.breaches || [];
    render(breaches.body, list.length
      ? el('div', { className: 'qf-panel-body' }, list.map((breach) => el('div', { className: 'qf-fault' }, [
        status({
          state: breach.severity === 'critical' ? 'failed' : 'degraded',
          label: breach.label, shape: 'dot-filled',
        }),
        el('span', { className: 'qf-fault-reason', text: breach.detail }),
        el('span', { className: 'qf-mono qf-caption', text: breach.code }),
      ])))
      : el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: 'Нарушений лимитов нет' }),
      ]));
  }

  function updateEvents(snapshot) {
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('riskEvents'), skeleton: 3 });
    if (fallback) { render(history.body, fallback); return; }
    if (!snapshot.hasData) return;
    if (!history.body.contains(historyTable.wrap)) history.body.replaceChildren(historyTable.wrap);
    historyTable.setRows(snapshot.data.events || []);
  }

  return {
    root,
    slices: ['risk', 'riskEvents'],
    mount() {
      const offRisk = context.subscribe('risk', updateRisk);
      const offEvents = context.subscribe('riskEvents', updateEvents);
      return () => { offRisk(); offEvents(); };
    },
    dispose() { historyTable.dispose(); },
  };
}

// ── Portfolio ────────────────────────────────────────────────────────────────

export function createPortfolio(context) {
  const accounts = panel({ title: 'Счета', flush: true });
  const stats = panel({ title: 'Показатели', flush: true });
  const allocation = panel({ title: 'Распределение', flush: true });
  const attribution = panel({ title: 'По инструментам', flush: true });

  const attributionTable = new DataTable(attribution.body, {
    caption: 'PnL по инструментам с размером выборки и долей прибыльных сделок.',
    storageKey: 'attribution',
    density: 'compact',
    columns: [
      { key: 'ticker', label: t('positions.ticker'), sortable: true,
        render: (row) => el('span', { className: 'qf-mono', text: row.ticker }) },
      { key: 'n', label: 'Сделок', numeric: true, sortable: true, render: (row) => fmt.integer(row.n) },
      { key: 'total_pnl', label: t('trades.pnl_money'), numeric: true, sortable: true,
        render: (row) => el('span', { className: fmt.signClass(row.total_pnl),
          text: fmt.money(row.total_pnl, { signed: true }) }) },
      { key: 'win_rate_pct', label: t('strategies.win_rate'), numeric: true, sortable: true,
        render: (row) => fmt.winRate(row.win_rate_pct, row.wins, row.n) },
      { key: 'mature_sample', label: 'Выборка',
        render: (row) => (row.mature_sample ? chip('достаточно', { tone: 'neutral' })
          : chip(t('strategies.immature'), { tone: 'unknown' })) },
    ],
    rowKey: (row) => row.ticker,
  });

  const root = el('div', { className: 'qf-view', dataset: { view: 'portfolio' } }, [
    accounts.root,
    stats.root,
    el('div', { className: 'qf-grid qf-grid--2' }, [allocation.root, attribution.root]),
  ]);

  function update(snapshot) {
    render(stats.meta, [freshnessMeta(snapshot.meta),
      snapshot.meta && snapshot.meta.n !== undefined ? el('span', { text: fmt.sampleSuffix(snapshot.meta.n) }) : null]);
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('portfolio'), skeleton: 5 });
    if (fallback) { render(stats.body, fallback); return; }
    if (!snapshot.hasData) return;

    const data = snapshot.data;

    // Each account named separately. «Общий баланс» merging a brokerage portfolio
    // and a paper account is how two irreconcilable numbers shared one label.
    render(accounts.body, el('div', { className: 'qf-panel-body' },
      (data.accounts || []).map((account) => el('div', { className: 'qf-panel' }, [
        el('div', { className: 'qf-panel-header' }, [
          el('h3', { className: 'qf-panel-title', text: account.name }),
          el('div', { className: 'qf-panel-meta' }, [
            environmentChip(account.environment),
            el('span', { className: 'qf-mono', text: account.source }),
          ]),
        ]),
        metricsGrid([
          moneyMetric({ label: 'Баланс', value: account.balance, currency: account.currency, signed: false }),
          moneyMetric({ label: 'Доступно', value: account.available_balance, currency: account.currency, signed: false }),
          moneyMetric({ label: 'Начальный', value: account.initial_balance, currency: account.currency, signed: false }),
          moneyMetric({ label: 'Маржа', value: account.margin_used, currency: account.currency, signed: false }),
          moneyMetric({ label: 'Итог', value: account.total_return_abs, currency: account.currency }),
          percentMetric({ label: 'Итог, %', value: account.total_return_pct }),
        ]),
        // An account whose available balance exceeds its total balance is
        // incoherent, and this database contains one. Surfacing it beats
        // displaying it under a confident label.
        (account.inconsistencies || []).length
          ? el('div', { className: 'qf-panel-body' }, account.inconsistencies.map((issue) =>
            el('div', { className: 'qf-status', dataset: { state: 'degraded' }, attrs: { role: 'alert' } }, [
              el('span', { className: 'qf-status-shape', dataset: { shape: 'dot-half' } }),
              el('span', { text: issue }),
            ])))
          : null,
      ]))));

    const s = data.statistics || {};
    const drawdown = data.drawdown || {};
    const ra = data.risk_adjusted || {};
    render(stats.body, metricsGrid([
      moneyMetric({ label: 'Реализованный PnL', value: s.total_pnl, n: s.n, currency: s.currency }),
      // The signed mean, and the absolute mean beside it under its own name.
      percentMetric({ label: 'Средний результат', value: s.avg_pnl_pct, n: s.avg_pnl_pct_n }),
      percentMetric({ label: 'Средний ход', value: s.avg_abs_move_pct, n: s.avg_pnl_pct_n, signed: false }),
      moneyMetric({ label: 'Средняя сделка', value: s.avg_pnl, n: s.avg_pnl_n, currency: s.currency }),
      metric({ label: t('strategies.win_rate'), value: fmt.winRate(s.win_rate_pct, s.wins, s.win_rate_n) }),
      metric({ label: t('strategies.profit_factor'),
        value: fmt.profitFactor(s.profit_factor, { n: s.profit_factor_n, undefinedReason: s.profit_factor_undefined_reason }),
        sub: s.profit_factor_undefined_reason || fmt.sampleSuffix(s.profit_factor_n) }),
      moneyMetric({ label: 'Ожидание на сделку', value: s.expectancy, n: s.expectancy_n, currency: s.currency }),
      moneyMetric({ label: 'Комиссии', value: s.commission_total, currency: s.currency, signed: false }),
      percentMetric({ label: t('risk.drawdown_max'), value: drawdown.max_drawdown_pct, n: drawdown.n }),
      // Sharpe is `null` below 20 daily observations rather than a noisy number.
      metric({ label: 'Sharpe',
        value: fmt.isNumber(ra.sharpe_ratio) ? fmt.number(ra.sharpe_ratio, 2) : fmt.NO_DATA,
        sub: ra.mature ? fmt.sampleSuffix(ra.n) : `мало данных ${fmt.MIDDOT} ${fmt.sampleSuffix(ra.n)}`,
        tone: ra.mature ? undefined : 'qf-unknown-value' }),
      metric({ label: 'Sortino',
        value: fmt.isNumber(ra.sortino_ratio) ? fmt.number(ra.sortino_ratio, 2) : fmt.NO_DATA,
        sub: ra.mature ? fmt.sampleSuffix(ra.n) : `мало данных`,
        tone: ra.mature ? undefined : 'qf-unknown-value' }),
      metric({ label: 'Средняя длительность', value: fmt.duration(s.avg_duration_seconds) }),
    ]));

    render(allocation.body, (data.allocation || []).length
      ? el('div', { className: 'qf-panel-body' }, (data.allocation || []).map((item) =>
        el('div', { className: 'qf-fault' }, [
          el('span', { className: 'qf-mono', text: item.label }),
          el('span', { className: 'qf-fault-reason qf-num',
            text: fmt.money(item.value, { signed: false }) }),
          el('span', { className: 'qf-fault-time', text: fmt.percent(item.pct, { signed: false }) }),
        ])))
      : el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.NO_POSITIONS') }),
      ]));

    if (!attribution.body.contains(attributionTable.wrap)) {
      attribution.body.replaceChildren(attributionTable.wrap);
    }
    attributionTable.setRows(data.attribution || []);
  }

  return {
    root,
    slices: ['portfolio'],
    mount() { return context.subscribe('portfolio', update); },
    dispose() { attributionTable.dispose(); },
  };
}

// ── Analytics ────────────────────────────────────────────────────────────────

export function createAnalytics(context) {
  const { charts } = context;
  const equity = chartPanel({ title: t('analytics.equity'), height: '260px' });
  const underwater = chartPanel({ title: t('analytics.underwater'), height: '160px' });
  const daily = chartPanel({ title: t('analytics.daily_pnl'), height: '200px' });
  const distribution = chartPanel({ title: t('analytics.distribution'), height: '200px' });

  const root = el('div', { className: 'qf-view', dataset: { view: 'analytics' } }, [
    el('div', { className: 'qf-panel-body qf-toolbar' }, []),
    equity.root, underwater.root,
    el('div', { className: 'qf-grid qf-grid--2' }, [daily.root, distribution.root]),
  ]);

  function bindTable(built, rows, columns) {
    render(built.tableHost, el('table', { className: 'qf-table qf-table--compact' }, [
      el('caption', { text: built.root.querySelector('.qf-panel-title').textContent }),
      el('thead', {}, [el('tr', {}, columns.map((c) => el('th', { text: c, attrs: { scope: 'col' } })))]),
      el('tbody', {}, rows.map((row) => el('tr', {}, row.map((cell) =>
        el('td', { text: cell, dataset: { align: 'end' } }))))),
    ]));
  }

  function updateEquity(snapshot) {
    render(equity.meta, [freshnessMeta(snapshot.meta)]);
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('equity'), skeleton: 3 });
    if (fallback) { render(equity.body, fallback); return; }
    if (!snapshot.hasData) return;

    const data = snapshot.data;
    const points = (data.points || []).map((p) => ({ ts: p.ts, value: p.equity }));
    const chart = charts.create('analytics-equity', LineChart, equity.chartHost, {
      showAxis: true, ariaLabel: t('analytics.equity'),
    });
    chart.setData(points);
    equity.summaryNode.textContent = seriesSummary(points, {
      currency: data.currency, label: t('analytics.equity'),
    });
    render(equity.meta, [
      freshnessMeta(snapshot.meta),
      el('span', { text: `${fmt.integer(points.length)} ${t('analytics.points')}` }),
      el('span', { text: `${fmt.integer(data.observations)} ${t('analytics.observations')}` }),
      el('span', {
        className: data.distinct_values < 60 && data.observations > 100 ? 'qf-stale' : '',
        text: `${fmt.integer(data.distinct_values)} ${t('analytics.distinct_values')}`,
        title: t('analytics.polling_artefact'),
      }),
      el('span', { text: data.window_label || '' }),
    ]);
    bindTable(equity, points.map((p) => [fmt.shortDateTime(p.ts), fmt.money(p.value, { currency: data.currency, signed: false })]),
      ['Время', 'Капитал']);
  }

  function updateUnderwater(snapshot) {
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('underwater'), skeleton: 2 });
    if (fallback) { render(underwater.body, fallback); return; }
    if (!snapshot.hasData) return;
    const points = (snapshot.data.points || []).map((p) => ({ ts: p.ts, value: p.drawdown_pct }));
    charts.create('analytics-underwater', UnderwaterChart, underwater.chartHost, {
      ariaLabel: t('analytics.underwater'),
    }).setData(points);
    const worst = points.length ? Math.min(...points.map((p) => p.value)) : null;
    underwater.summaryNode.textContent = points.length
      ? `Максимальная просадка за окно: ${fmt.percent(worst)}. Точек: ${fmt.integer(points.length)}.`
      : 'Нет данных для расчёта просадки.';
    bindTable(underwater, points.map((p) => [fmt.shortDateTime(p.ts), fmt.percent(p.value)]),
      ['Время', 'Просадка']);
  }

  function updateDaily(snapshot) {
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('dailyPnl'), skeleton: 2 });
    if (fallback) { render(daily.body, fallback); return; }
    if (!snapshot.hasData) return;
    const bars = (snapshot.data.points || []).map((p) => ({ label: p.day, value: p.pnl }));
    charts.create('analytics-daily', BarChart, daily.chartHost, { ariaLabel: t('analytics.daily_pnl') })
      .setData(bars);
    const total = bars.reduce((sum, b) => sum + (b.value || 0), 0);
    daily.summaryNode.textContent = bars.length
      ? `${fmt.integer(bars.length)} дней, суммарно ${fmt.money(total, { signed: true })}.`
      : t('state.NO_TRADES_IN_PERIOD');
    bindTable(daily, bars.map((b) => [b.label, fmt.money(b.value, { signed: true })]), ['День', 'PnL']);
  }

  function updateDistribution(snapshot) {
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('distribution'), skeleton: 2 });
    if (fallback) { render(distribution.body, fallback); return; }
    if (!snapshot.hasData) return;
    const data = snapshot.data;
    charts.create('analytics-distribution', Histogram, distribution.chartHost, {
      ariaLabel: t('analytics.distribution'),
    }).setData(data.bins || []);
    render(distribution.meta, [
      el('span', { text: fmt.sampleSuffix(data.n) }),
      data.bin_width !== null && data.bin_width !== undefined
        ? el('span', { text: `${t('analytics.bin_width')} ${fmt.money(data.bin_width, { signed: false })}` })
        : null,
    ]);
    distribution.summaryNode.textContent = (data.bins || []).length
      ? `Распределение PnL по ${fmt.integer(data.bins.length)} интервалам, ${fmt.sampleSuffix(data.n)}.`
      : t('state.NO_TRADES_EVER');
    bindTable(distribution, (data.bins || []).map((b) =>
      [`${fmt.money(b.from, { signed: false })} … ${fmt.money(b.to, { signed: false })}`, fmt.integer(b.count)]),
      ['Интервал', 'Сделок']);
  }

  return {
    root,
    slices: ['equity', 'underwater', 'dailyPnl', 'distribution'],
    mount() {
      const offs = [
        context.subscribe('equity', updateEquity),
        context.subscribe('underwater', updateUnderwater),
        context.subscribe('dailyPnl', updateDaily),
        context.subscribe('distribution', updateDistribution),
      ];
      return () => offs.forEach((off) => off());
    },
    dispose() {
      for (const key of ['analytics-equity', 'analytics-underwater', 'analytics-daily', 'analytics-distribution']) {
        charts.destroy(key);
      }
    },
  };
}

// ── Health ───────────────────────────────────────────────────────────────────

export const createHealth = tableScreen({
  title: t('health.title'),
  slice: 'health',
  storageKey: 'health',
  density: 'comfortable',
  tableCaption: 'Сервисы: состояние с формой индикатора, причина, рекомендованное действие и время проверки.',
  metrics: (data) => metricsGrid([
    metric({ label: 'Сервисов', value: fmt.integer((data.services || []).length) }),
    metric({ label: t('health.collector_stale'),
      value: fmt.isNumber(data.collector_age_seconds) ? fmt.age(data.collector_age_seconds) : fmt.NO_DATA,
      tone: !fmt.isNumber(data.collector_age_seconds) || data.collector_age_seconds > 300 ? 'qf-negative' : undefined }),
    metric({ label: t('health.latency_p50'), value: fmt.latency(data.latency && data.latency.p50_ms),
      sub: fmt.sampleSuffix(data.latency && data.latency.n) }),
    metric({ label: t('health.latency_p95'), value: fmt.latency(data.latency && data.latency.p95_ms) }),
  ]),
  rows: (data) => data.services || [],
  rowKey: (row) => row.key,
  columns: () => [
    { key: 'name', label: t('health.service') },
    { key: 'state', label: t('health.state'),
      render: (row) => status({ state: row.state, label: row.label, shape: row.shape }) },
    { key: 'reason', label: t('health.reason'),
      render: (row) => el('span', { className: 'qf-truncate', text: row.reason || '—', title: row.reason }) },
    { key: 'action', label: t('health.action'),
      render: (row) => el('span', { className: 'qf-caption', text: row.action || '—' }) },
    { key: 'data_age_seconds', label: 'Возраст данных', numeric: true,
      render: (row) => (fmt.isNumber(row.data_age_seconds)
        ? el('span', { className: 'qf-stale', text: fmt.age(row.data_age_seconds) })
        : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
    { key: 'checked_at', label: t('health.checked'), numeric: true,
      render: (row) => el('span', { className: 'qf-mono', text: fmt.smartTime(row.checked_at) }) },
  ],
});

// ── Event log ────────────────────────────────────────────────────────────────

export const createEvents = tableScreen({
  title: t('events.title'),
  slice: 'events',
  storageKey: 'events',
  density: 'compact',
  tableCaption: 'Системные события: время, уровень, источник, сообщение и correlation id.',
  filters: (context, params, setParam) => [
    selectFilter({ id: 'events-level', label: t('events.level'), includeAll: true,
      options: [['ERROR', 'ERROR'], ['WARN', 'WARN'], ['INFO', 'INFO'], ['DEBUG', 'DEBUG']],
      value: params.level || '', onChange: (v) => setParam('level', v) }),
    textFilter({ id: 'events-q', label: t('events.search'), value: params.q,
      onChange: (v) => setParam('q', v) }),
    textFilter({ id: 'events-cid', label: t('events.correlation'), value: params.correlation_id,
      onChange: (v) => setParam('correlation_id', v) }),
  ],
  metrics: (data) => metricsGrid(Object.entries(data.level_census || {}).map(([level, count]) =>
    metric({ label: level, value: fmt.integer(count), sub: 'за 24 ч',
      tone: level === 'ERROR' ? 'qf-negative' : level === 'WARN' ? 'qf-unknown-value' : undefined }))),
  rows: (data) => data.events || [],
  columns: () => [
    { key: 'created_at', label: 'Время', sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: fmt.smartTime(row.created_at),
        title: fmt.absoluteTime(row.created_at) }) },
    { key: 'level', label: t('events.level'), sortable: true,
      render: (row) => chip(row.level, {
        tone: row.level === 'ERROR' || row.level === 'CRITICAL' ? 'negative'
          : row.level === 'WARN' ? 'warning' : 'neutral',
      }) },
    { key: 'source', label: t('events.source'), sortable: true,
      render: (row) => el('span', { className: 'qf-mono', text: row.source }) },
    { key: 'category', label: 'Категория',
      render: (row) => el('span', { className: 'qf-caption', text: row.category || '—' }) },
    { key: 'message', label: t('events.message'),
      render: (row) => el('span', { className: 'qf-truncate', text: row.message, title: row.message }) },
    { key: 'correlation_id', label: t('events.correlation'),
      render: (row) => el('span', { className: 'qf-mono qf-truncate', text: row.correlation_id || '—',
        title: row.correlation_id }) },
  ],
});

// ── Backtest ─────────────────────────────────────────────────────────────────

export function createBacktest(context) {
  const { charts } = context;
  const form = panel({ title: t('backtest.title') });
  const results = panel({ title: 'Результат', flush: true });
  const equity = chartPanel({ title: t('analytics.equity'), height: '220px' });

  const fields = {};
  function field(id, label, value, type = 'text') {
    const input = el('input', { className: 'qf-input', attrs: { id, type, value } });
    fields[id] = input;
    return el('div', { className: 'qf-field' }, [
      el('label', { className: 'qf-field-label', text: label, attrs: { for: id } }),
      input,
    ]);
  }

  const runButton = actionButton({
    label: t('backtest.run'),
    primary: true,
    permitted: context.session.can('run_backtest'),
    reason: context.session.denialReason('run_backtest'),
    onClick: run,
  });

  render(form.body, [
    el('div', { className: 'qf-grid qf-grid--4' }, [
      field('bt-ticker', t('backtest.ticker'), 'SBER'),
      field('bt-strategy', t('backtest.strategy'), 'rules_engine'),
      field('bt-start', `${t('backtest.period')} c`, '', 'date'),
      field('bt-end', `${t('backtest.period')} по`, '', 'date'),
      field('bt-capital', t('backtest.capital'), '1000000', 'number'),
      field('bt-risk', t('backtest.risk'), '0.05', 'number'),
      field('bt-commission', t('backtest.commission'), '0.0003', 'number'),
      field('bt-slippage', t('backtest.slippage'), '0.0001', 'number'),
    ]),
    el('div', { className: 'qf-toolbar' }, [runButton]),
  ]);

  render(results.body, el('div', { className: 'qf-state' }, [
    el('div', { className: 'qf-state-title', text: t('backtest.ready') }),
    el('div', { className: 'qf-state-detail', text: t('backtest.ready_hint') }),
  ]));

  async function run() {
    // A compute action needs a visible in-flight state and a real error path.
    // The old button had neither, and `window.QFToast` was never defined so both
    // success and failure were invisible.
    runButton.disabled = true;
    runButton.setAttribute('aria-busy', 'true');
    runButton.textContent = t('backtest.running');
    render(results.body, el('div', { className: 'qf-state' }, [
      el('div', { className: 'qf-state-title', text: t('backtest.running') }),
    ]));

    try {
      const { data } = await context.api.runBacktest({
        ticker: fields['bt-ticker'].value.trim().toUpperCase(),
        strategy: fields['bt-strategy'].value.trim(),
        period_start: fields['bt-start'].value || null,
        period_end: fields['bt-end'].value || null,
        initial_capital: Number(fields['bt-capital'].value),
        risk_pct: Number(fields['bt-risk'].value),
        commission_pct: Number(fields['bt-commission'].value),
        slippage_pct: Number(fields['bt-slippage'].value),
      });
      renderResult(data);
      toasts.success(`${t('backtest.title')}: ${fmt.integer(data.total_trades)} ${t('backtest.trades').toLowerCase()}`);
    } catch (error) {
      render(results.body, el('div', { className: 'qf-state qf-state--error', attrs: { role: 'alert' } }, [
        el('div', { className: 'qf-state-title', text: t('action.failed') }),
        el('div', { className: 'qf-state-detail', text: error.message }),
        error.correlationId
          ? el('div', { className: 'qf-state-id', text: `${t('state.error_id')}: ${error.correlationId}` })
          : null,
      ]));
      toasts.error(error.message, error.correlationId);
    } finally {
      runButton.disabled = !context.session.can('run_backtest');
      runButton.removeAttribute('aria-busy');
      runButton.textContent = t('backtest.run');
    }
  }

  function renderResult(data) {
    render(results.body, metricsGrid([
      metric({ label: t('backtest.trades'), value: fmt.integer(data.total_trades),
        sub: fmt.sampleSuffix(data.total_trades) }),
      moneyMetric({ label: 'Итоговый PnL', value: data.total_pnl }),
      moneyMetric({ label: 'Итоговый баланс', value: data.final_balance, signed: false }),
      metric({ label: t('strategies.win_rate'), value: fmt.percent(data.win_rate, { signed: false }),
        sub: fmt.sampleSuffix(data.total_trades) }),
      metric({ label: t('strategies.profit_factor'), value: fmt.number(data.profit_factor, 2) }),
      percentMetric({ label: t('risk.drawdown_max'), value: data.max_drawdown, signed: true }),
      metric({ label: 'Sharpe', value: fmt.number(data.sharpe_ratio, 2),
        sub: data.total_trades < 30 ? t('strategies.immature') : fmt.sampleSuffix(data.total_trades),
        tone: data.total_trades < 30 ? 'qf-unknown-value' : undefined }),
      metric({ label: 'Инструмент', value: data.ticker }),
    ]));

    const points = (data.equity_curve || []).map((point, index) => ({
      ts: point.ts || String(index),
      value: typeof point === 'number' ? point : (point.equity ?? point.value),
    })).filter((p) => fmt.isNumber(p.value));
    charts.create('backtest-equity', LineChart, equity.chartHost, { showAxis: false })
      .setData(points);
    equity.summaryNode.textContent = seriesSummary(points, { label: t('analytics.equity') });
  }

  const root = el('div', { className: 'qf-view', dataset: { view: 'backtest' } },
    [form.root, results.root, equity.root]);

  return {
    root,
    slices: [],
    mount() { return () => {}; },
    dispose() { charts.destroy('backtest-equity'); },
  };
}

// ── Settings ─────────────────────────────────────────────────────────────────

export function createSettings(context) {
  const profile = panel({ title: t('settings.profile') });
  const display = panel({ title: t('settings.display') });
  const brokers = panel({ title: t('settings.brokers'), flush: true });
  const limits = panel({ title: t('settings.limits'), flush: true });

  const root = el('div', { className: 'qf-view', dataset: { view: 'settings' } }, [
    el('div', { className: 'qf-grid qf-grid--2' }, [profile.root, display.root]),
    brokers.root, limits.root,
  ]);

  function renderProfile() {
    const user = context.session.user || {};
    render(profile.body, [
      metricsGrid([
        metric({ label: 'Пользователь', value: user.display_name || user.username || fmt.NO_DATA }),
        metric({ label: 'Роль', value: user.role_label || fmt.NO_DATA }),
        metric({ label: 'Торговые действия',
          value: user.trading_authorized ? t('common.yes') : t('common.no'),
          tone: user.trading_authorized ? undefined : 'qf-unknown-value' }),
      ]),
      el('div', { className: 'qf-toolbar' }, [
        el('button', {
          className: 'qf-btn', text: t('settings.change_password'), attrs: { type: 'button' },
          on: { click: () => context.changePassword() },
        }),
        el('button', {
          className: 'qf-btn', text: t('shell.logout'), attrs: { type: 'button' },
          on: { click: () => context.logout() },
        }),
      ]),
    ]);
  }

  function renderDisplay() {
    render(display.body, [
      el('div', { className: 'qf-field' }, [
        el('label', { className: 'qf-field-label', text: t('settings.density'), attrs: { for: 'set-density' } }),
        (() => {
          const select = el('select', { className: 'qf-select', attrs: { id: 'set-density' } });
          for (const [value, label] of [
            ['compact', t('settings.density.compact')],
            ['comfortable', t('settings.density.comfortable')],
            ['monitoring', t('settings.density.monitoring')],
          ]) {
            select.appendChild(el('option', { text: label, attrs: { value, selected: context.density() === value } }));
          }
          select.addEventListener('change', () => context.setDensity(select.value));
          return select;
        })(),
      ]),
      el('div', { className: 'qf-field' }, [
        el('label', { className: 'qf-field-label', text: t('settings.shortcuts_enabled'), attrs: { for: 'set-shortcuts' } }),
        (() => {
          const box = el('input', {
            attrs: { id: 'set-shortcuts', type: 'checkbox', checked: context.shortcutsEnabled() },
          });
          box.addEventListener('change', () => context.setShortcutsEnabled(box.checked));
          return box;
        })(),
      ]),
      el('div', {}, [
        el('h3', { text: t('shell.shortcuts') }),
        el('ul', {}, context.shortcuts().map((item) =>
          el('li', { className: 'qf-caption', text: `${item.key} — ${item.description}` }))),
      ]),
    ]);
  }

  function updateCredentials(snapshot) {
    const fallback = stateFor(snapshot, { onRetry: () => context.refresh('credentials'), skeleton: 3 });
    if (fallback) { render(brokers.body, fallback); return; }
    if (!snapshot.hasData) return;

    const canManage = context.session.can('manage_credentials');
    render(brokers.body, el('div', { className: 'qf-panel-body' }, [
      el('p', { className: 'qf-state-detail', text: t('settings.credential_never_shown') }),
      ...(snapshot.data.credentials || []).map((credential) => el('div', { className: 'qf-fault' }, [
        el('span', { className: 'qf-fault-subject', text: credential.label }),
        el('span', { className: 'qf-mono qf-caption', text: credential.key }),
        status({
          state: credential.configured ? 'healthy' : 'unknown',
          label: credential.configured ? t('settings.configured') : t('settings.not_configured'),
          shape: credential.configured ? 'dot-filled' : 'ring-dashed',
        }),
        // A length, not a masked prefix: even four leading characters of a broker
        // token is a material disclosure on a screen that may be screenshotted.
        el('span', { className: 'qf-fault-time',
          text: credential.configured ? `${fmt.integer(credential.length)} симв.` : '—' }),
        actionButton({
          label: t('settings.clear'),
          danger: true,
          permitted: canManage && credential.configured,
          reason: canManage ? 'Значение не задано.' : context.session.denialReason('manage_credentials'),
          onClick: () => context.clearCredential(credential.key, credential.label),
        }),
      ])),
    ]));
  }

  function updateLimits(snapshot) {
    if (!snapshot.hasData) return;
    const data = snapshot.data;
    const sizing = data.sizing || {};
    const daily = data.daily || {};
    render(limits.body, metricsGrid([
      data.positions.limit_configured
        ? metric({ label: 'Макс. открытых позиций', value: fmt.integer(data.positions.limit),
          sub: 'config.risk.max_open_positions' })
        : metric({ label: 'Макс. открытых позиций', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
      daily.limit_pct && daily.limit_pct.configured
        ? percentMetric({ label: 'Дневной лимит убытка', value: -Math.abs(daily.limit_pct.value) })
        : metric({ label: 'Дневной лимит убытка', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
      sizing.max_position_pct && sizing.max_position_pct.configured
        ? percentMetric({ label: 'Макс. размер позиции', value: sizing.max_position_pct.value, signed: false })
        : metric({ label: 'Макс. размер позиции', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
      sizing.atr_stop_multiplier && sizing.atr_stop_multiplier.configured
        ? metric({ label: 'ATR-множитель стопа', value: fmt.number(sizing.atr_stop_multiplier.value, 1) })
        : metric({ label: 'ATR-множитель стопа', value: t('risk.not_configured'), tone: 'qf-unknown-value' }),
    ]));
  }

  return {
    root,
    slices: ['credentials', 'risk'],
    mount() {
      renderProfile();
      renderDisplay();
      const offs = [
        context.subscribe('credentials', updateCredentials),
        context.subscribe('risk', updateLimits),
      ];
      return () => offs.forEach((off) => off());
    },
    dispose() {},
  };
}
