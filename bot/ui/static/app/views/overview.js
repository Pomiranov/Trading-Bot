/**
 * Overview — the five-second screen.
 *
 * Order is the whole design. A trader opening the terminal asks, in this order:
 * is the system running and is what I'm looking at current; am I exposed and how
 * badly can it hurt; did anything happen that I must act on; and only then, how
 * is the account doing. The old Overview answered those in reverse — its first
 * and largest element was ОБЩИЙ БАЛАНС, engine state was absent, sandbox-vs-live
 * was absent, and freshness was a grey timestamp that lied.
 *
 * Above the fold at 1440×900: environment band, fault region, risk & exposure,
 * open positions, capital, last signal + gate, health strip. Removed: the
 * four-across PnL tile row (three of them read `+0,00 ₽`), the Sharpe tile
 * (`—`), and the oversized balance tile.
 */

import { LineChart, Sparkline, seriesSummary } from '../charts.js';
import { append, el, render } from '../dom.js';
import * as fmt from '../format.js';
import { t } from '../i18n.js';
import { DataTable } from '../table.js';
import {
  actionButton, chip, confidenceValue, environmentChip, freshnessMeta, metric,
  metricsGrid, moneyMetric, panel, partialNote, percentMetric, stateFor, status,
} from '../ui.js';

export function createOverview(context) {
  const { charts, session, onAction, onNavigate } = context;

  const risk = panel({ title: t('overview.risk') });
  const positions = panel({ title: t('overview.positions'), flush: true });
  const capital = panel({ title: t('overview.capital') });
  const signal = panel({ title: t('overview.last_signal') });
  const health = panel({ title: t('overview.health'), flush: true });

  // The table gets its own host inside the panel body. Building it directly on
  // `positions.body` meant the first loading state — which replaces the body's
  // children — evicted the table's own node, and every later `setRows` wrote into
  // a detached tbody. The panel then showed a skeleton forever while the data sat
  // in the store.
  const positionsHost = el('div');
  render(positions.body, positionsHost);
  const positionsTable = new DataTable(positionsHost, {
    caption: 'Открытые позиции: тикер, направление, размер, вход, текущая цена с её возрастом, расстояние до стопа, нереализованный PnL, стратегия и среда.',
    storageKey: 'overview-positions',
    density: 'comfortable',
    columns: positionColumns(),
    rowKey: (row) => row.id,
  });

  const equitySparkline = charts.create('overview-equity', Sparkline,
    el('div', { className: 'qf-chart qf-sparkline' }));

  const root = el('div', { className: 'qf-view', dataset: { view: 'overview' } }, [
    el('div', { className: 'qf-grid qf-grid--risk-positions' }, [risk.root, positions.root]),
    el('div', { className: 'qf-grid qf-grid--2' }, [capital.root, signal.root]),
    health.root,
  ]);

  function positionColumns() {
    return [
      { key: 'ticker', label: t('positions.ticker'), sortable: true,
        render: (row) => el('span', { className: 'qf-mono', text: row.ticker }) },
      { key: 'direction', label: t('positions.direction'),
        render: (row) => chip(row.direction === 'short' ? 'SHORT' : 'LONG',
          { tone: row.direction === 'short' ? 'negative' : 'positive' }) },
      { key: 'quantity', label: t('positions.quantity'), numeric: true,
        render: (row) => fmt.quantity(row.quantity, t('unit.pieces')) },
      { key: 'entry_price', label: t('positions.entry'), numeric: true,
        render: (row) => fmt.price(row.entry_price) },
      // Mark price carries its own age. The cell is stale, not the panel.
      { key: 'mark_price', label: t('positions.mark'), numeric: true,
        stale: (row) => row.mark_is_stale === true,
        title: (row) => row.mark_as_of || t('positions.no_quote'),
        render: (row) => {
          if (row.mark_price === null || row.mark_price === undefined) {
            return el('span', { className: 'qf-unknown-value', text: t('positions.no_quote') });
          }
          const wrap = el('span', { className: 'qf-num' }, [
            el('span', { text: fmt.price(row.mark_price) }),
          ]);
          if (row.mark_is_stale) {
            append(wrap, el('span', {
              className: 'qf-stale',
              text: ` ${fmt.age(row.mark_age_seconds)}`,
              title: row.mark_as_of ? fmt.absoluteTime(row.mark_as_of) : undefined,
            }));
          }
          return wrap;
        } },
      // Distance to stop, not a second price column: it is the only number on the
      // row that says how much room the position has, and the old UI made the
      // trader subtract two prices to find it.
      { key: 'distance_to_stop_pct', label: t('positions.distance_to_stop'), numeric: true, sortable: true,
        render: (row) => (fmt.isNumber(row.distance_to_stop_pct)
          ? el('span', { className: fmt.signClass(-Math.abs(row.distance_to_stop_pct)), text: fmt.percent(row.distance_to_stop_pct) })
          : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
      { key: 'unrealized_pnl', label: t('positions.unrealized'), numeric: true, sortable: true,
        render: (row) => (fmt.isNumber(row.unrealized_pnl)
          ? el('span', { className: fmt.signClass(row.unrealized_pnl), text: fmt.money(row.unrealized_pnl, { signed: true }) })
          : el('span', { className: 'qf-unknown-value', text: fmt.NO_DATA })) },
      { key: 'strategy_id', label: t('positions.strategy'),
        render: (row) => el('span', {
          className: 'qf-mono qf-truncate',
          text: row.strategy_id || fmt.NO_DATA,
          title: row.strategy_id || undefined,
        }) },
      { key: 'environment', label: t('positions.environment'),
        render: (row) => environmentChip(row.environment) },
    ];
  }

  function renderRisk(data) {
    if (!data || !data.exposure) {
      render(risk.body, el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.NOT_CONFIGURED') }),
      ]));
      return;
    }
    const currency = data.currency || 'RUB';
    const positionsInfo = data.positions || {};
    const drawdown = data.drawdown || {};
    const daily = data.daily || {};
    const risked = data.capital_at_risk || {};

    render(risk.body, [
      metricsGrid([
        moneyMetric({
          label: t('risk.exposure'), value: data.exposure.abs, currency, signed: false,
        }),
        percentMetric({
          label: `${t('risk.exposure')}, %`, value: data.exposure.pct, signed: false,
        }),
        moneyMetric({
          label: t('risk.capital_at_risk'), value: risked.abs, currency, signed: false,
        }),
        metric({
          label: t('risk.positions'),
          value: positionsInfo.limit_configured
            ? `${fmt.integer(positionsInfo.open)} / ${fmt.integer(positionsInfo.limit)}`
            : fmt.integer(positionsInfo.open),
          sub: positionsInfo.limit_configured ? undefined : t('risk.not_configured'),
        }),
        // Both drawdown units, side by side. The single ambiguous field that
        // rendered −23,73 % as «−0,2 %» no longer exists.
        percentMetric({
          label: t('risk.drawdown_max'), value: drawdown.max_pct,
          n: drawdown.n, window: drawdown.window_label,
        }),
        moneyMetric({
          label: `${t('risk.drawdown_max')}, ${fmt.currencySymbol(currency)}`,
          value: drawdown.max_abs, currency, n: drawdown.n,
        }),
        // A limit that is not configured says so. Never 0.
        daily.limit_pct && daily.limit_pct.configured
          ? metric({
            label: t('risk.daily_limit'),
            value: fmt.percent(-Math.abs(daily.limit_pct.value), { signed: true }),
            sub: fmt.isNumber(daily.limit_abs_derived)
              ? `${fmt.money(daily.limit_abs_derived, { currency })} ${fmt.MIDDOT} ${t('risk.derived')}`
              : t('risk.derived'),
          })
          : metric({
            label: t('risk.daily_limit'), value: t('risk.not_configured'),
            tone: 'qf-unknown-value',
          }),
        metric({
          label: t('risk.stale_marks'),
          value: fmt.integer(positionsInfo.stale_marks || 0),
          tone: positionsInfo.stale_marks ? 'qf-negative' : undefined,
          sub: risked.positions_without_stop
            ? `${fmt.integer(risked.positions_without_stop)} ${t('risk.no_stop')}`
            : undefined,
        }),
      ]),
      (data.breaches || []).length
        ? el('div', { className: 'qf-panel-body' }, (data.breaches || []).map((breach) =>
          el('div', { className: 'qf-status', dataset: { state: breach.severity === 'critical' ? 'failed' : 'degraded' } }, [
            el('span', { className: 'qf-status-shape', dataset: { shape: 'dot-filled' } }),
            el('span', { text: `${breach.label} — ${breach.detail}` }),
          ])))
        : null,
    ]);
  }

  function renderCapital(equity, pnl, snapshotMeta) {
    const currency = (equity && equity.currency) || 'RUB';
    const points = ((equity && equity.points) || []).map((p) => ({ ts: p.ts, value: p.equity }));
    const windows = (pnl && pnl.windows) || {};
    const day = windows.day || {};

    const sparkHost = el('div', { className: 'qf-chart qf-sparkline' });

    render(capital.body, [
      metricsGrid([
        moneyMetric({
          label: t('overview.capital'), value: equity && equity.last_equity,
          currency, signed: false, large: true,
        }),
        moneyMetric({
          label: `PnL ${day.label || 'сегодня'}`, value: day.pnl, n: day.n, currency,
        }),
        moneyMetric({
          label: `PnL ${(equity && equity.window_label) || ''}`,
          value: equity && equity.change_abs, currency,
          n: equity && equity.observations,
        }),
        percentMetric({
          label: `Изменение, %`, value: equity && equity.change_pct,
          window: equity && equity.window_label,
        }),
      ]),
      el('div', { className: 'qf-panel-body' }, [
        sparkHost,
        el('p', {
          className: 'qf-chart-summary',
          text: seriesSummary(points, { currency, label: t('analytics.equity') }),
        }),
        // A series with few distinct values is a polling artefact, and saying so
        // is more useful than drawing it as if it were a market.
        equity && equity.observations > 100 && equity.distinct_values < 60
          ? el('p', { className: 'qf-state-detail', text: t('analytics.polling_artefact') })
          : null,
      ]),
    ]);

    const chart = charts.create('overview-equity', Sparkline, sparkHost);
    chart.setData(points);
  }

  function renderSignal(latest, gate) {
    if (!latest) {
      render(signal.body, el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.NO_SIGNALS') }),
        gate && gate.gate_recording_note
          ? el('div', { className: 'qf-state-detail', text: gate.gate_recording_note })
          : null,
      ]));
      return;
    }

    render(signal.body, [
      el('div', { className: 'qf-toolbar' }, [
        el('span', { className: 'qf-mono', text: fmt.smartTime(latest.occurred_at) }),
        el('span', { className: 'qf-mono', text: latest.ticker || fmt.NO_DATA }),
        latest.direction ? chip(latest.direction, {
          tone: latest.direction === 'SHORT' ? 'negative' : 'positive',
        }) : null,
        latest.strategy_id
          ? el('span', { className: 'qf-mono qf-truncate', text: latest.strategy_id, title: latest.strategy_id })
          : null,
        environmentChip(latest.environment),
      ]),
      el('div', { className: 'qf-toolbar' }, [
        // The gate decision, its stage and the human reason — the answer to
        // "why was this rejected", which had no data behind it at all.
        status({
          state: latest.gate_tone === 'positive' ? 'healthy'
            : latest.gate_tone === 'negative' ? 'failed'
              : latest.gate_tone === 'warning' ? 'degraded' : 'unknown',
          label: latest.gate_decision_label,
          shape: latest.gate_tone === 'unknown' ? 'ring-dashed' : 'dot-filled',
        }),
        el('span', { className: 'qf-caption', text: latest.gate_stage_label }),
      ]),
      el('p', {
        className: latest.gate_reason_missing ? 'qf-state-detail' : 'qf-body',
        text: latest.gate_reason || t('signals.reason_missing'),
      }),
      // Confidence never appears without its sample size.
      fmt.isNumber(latest.confidence)
        ? el('div', {}, [confidenceValue(latest.confidence, latest.sample_size,
          { mature: latest.confidence_is_mature })])
        : null,
      latest.source_candle_at
        ? el('div', { className: 'qf-caption' }, [
          el('span', { text: `${t('signals.candle_age')}: ` }),
          latest.source_candle_stale
            ? el('span', { className: 'qf-stale', text: fmt.age(latest.source_candle_age_seconds),
              title: fmt.absoluteTime(latest.source_candle_at) })
            : el('span', { text: fmt.age(latest.source_candle_age_seconds) }),
        ])
        : null,
    ]);
  }

  function renderHealth(payload) {
    const services = (payload && payload.services) || [];
    if (!services.length) {
      render(health.body, el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.NOT_CONFIGURED') }),
      ]));
      return;
    }
    const collectorAge = payload.collector_age_seconds;
    render(health.body, [
      el('div', { className: 'qf-panel-body qf-toolbar' }, services.map((service) => status({
        state: service.state,
        label: `${service.name} ${service.label}`,
        shape: service.shape,
        title: [service.reason, service.action].filter(Boolean).join(' · ') || undefined,
      }))),
      // Health that has itself gone stale must be visible as such, or the strip
      // becomes decoration.
      collectorAge === null || collectorAge > 300
        ? el('div', { className: 'qf-panel-body' }, [
          el('span', {
            className: 'qf-stale',
            text: `${t('health.collector_stale')}: ${collectorAge === null ? fmt.NO_DATA : fmt.ageAgo(collectorAge)}`,
          }),
        ])
        : null,
      payload.latency && payload.latency.n
        ? el('div', { className: 'qf-panel-body qf-caption' }, [
          el('span', { text: `${t('analytics.latency')} — ${t('health.latency_p50')} ${fmt.latency(payload.latency.p50_ms)}, ${t('health.latency_p95')} ${fmt.latency(payload.latency.p95_ms)} (${fmt.sampleSuffix(payload.latency.n)})` }),
        ])
        : null,
    ]);
  }

  function update(snapshot) {
    const busy = snapshot.state === 'refreshing' || snapshot.state === 'loading';
    for (const built of [risk, positions, capital, signal, health]) {
      built.root.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    const fallback = stateFor(snapshot, {
      onRetry: () => context.refresh('overview'),
      skeleton: 4,
    });
    if (fallback && !snapshot.hasData) {
      render(risk.body, fallback);
      render(positionsHost, fallback.cloneNode(true));
      render(capital.body, fallback.cloneNode(true));
      render(signal.body, fallback.cloneNode(true));
      render(health.body, fallback.cloneNode(true));
      return;
    }
    if (!snapshot.hasData) return;

    const data = snapshot.data;
    renderRisk(data.risk);
    // Re-attach after a loading state replaced the host's children.
    if (!positionsHost.contains(positionsTable.wrap)) {
      positionsHost.replaceChildren(positionsTable.wrap);
    }
    positionsTable.setRows((data.positions && data.positions.positions) || []);
    // The panel header carries the count and the quote freshness, so «1 из 5» and
    // «71 мин» are visible without opening a row.
    render(positions.meta, [
      el('span', { text: `${fmt.integer((data.positions && data.positions.count) || 0)}` }),
      (data.positions && data.positions.stale_quote_count)
        ? el('span', { className: 'qf-stale', text: `${fmt.integer(data.positions.stale_quote_count)} устар.` })
        : null,
    ]);
    renderCapital(data.equity, data.pnl, snapshot.meta);
    render(capital.meta, [freshnessMeta(snapshot.meta)]);
    renderSignal(data.latest_signal, data.gate);
    renderHealth(data.health);

    const note = partialNote(snapshot.meta && snapshot.meta.missing);
    if (note) append(health.body, note);
  }

  return {
    root,
    slices: ['overview'],
    mount() {
      return context.subscribe('overview', update);
    },
    dispose() {
      positionsTable.dispose();
      charts.destroy('overview-equity');
    },
  };
}
