/**
 * Shared components: panels, metrics, status, data states, toasts and dialogs.
 *
 * Every data region gets its state from one function here, so the ten states can
 * never be partially implemented per screen. `window.QFToast` was referenced twice
 * in the old client and never defined, so the "Run Cycle" button gave no feedback
 * at all on either success or failure.
 */

import { append, el, icon, render, svg, trapFocus } from './dom.js';
import * as fmt from './format.js';
import { emptyReasonText, errorText, t } from './i18n.js';
import { SliceState } from './store.js';

// ── Panels ───────────────────────────────────────────────────────────────────

/**
 * A panel with a header, optional meta and a body.
 *
 * The body node is returned separately so a renderer can replace only the body,
 * which is what keeps a refresh from blanking the header and the panel from
 * changing height as data arrives.
 */
export function panel({ title, meta, actions, flush = false, chartHeight } = {}) {
  const body = el('div', {
    className: flush ? 'qf-panel-body qf-panel-body--flush' : 'qf-panel-body',
  });
  const metaNode = el('div', { className: 'qf-panel-meta' });
  const header = el('div', { className: 'qf-panel-header' }, [
    el('h2', { className: 'qf-panel-title', text: title }),
    metaNode,
  ]);
  if (actions) append(metaNode, actions);
  if (meta) append(metaNode, el('span', { text: meta }));

  const root = el('div', {
    className: 'qf-panel',
    style: chartHeight ? { '--qf-chart-height': chartHeight } : undefined,
  }, [header, body]);

  return { root, body, header, meta: metaNode };
}

/**
 * The freshness line for a panel header.
 *
 * Always says which of three things is true: fresh (with the age), stale (with the
 * age and a marker), or unknown. There is no fourth rendering, and no silence.
 */
export function freshnessMeta(sliceMeta) {
  if (!sliceMeta) return el('span', { className: 'qf-stale', text: t('state.loading') });
  const age = sliceMeta.data_age_seconds;
  const stale = typeof sliceMeta.is_stale === 'boolean'
    ? sliceMeta.is_stale
    : fmt.isStale(age, sliceMeta.stale_after_seconds);
  const absolute = sliceMeta.source_as_of
    ? fmt.absoluteTime(sliceMeta.source_as_of, sliceMeta.timezone || 'MSK')
    : null;

  if (age === null || age === undefined) {
    return el('span', {
      className: 'qf-stale',
      text: 'возраст неизвестен',
      title: 'Источник не сообщил время последнего обновления.',
    });
  }
  if (stale) {
    return el('span', { className: 'qf-stale', text: fmt.age(age), title: absolute || undefined });
  }
  return el('span', { text: fmt.age(age), title: absolute || undefined });
}

/** Sample size as a header note: `n = 35`. */
export function sampleMeta(n) {
  return el('span', { text: fmt.sampleSuffix(n) });
}

// ── Metrics ──────────────────────────────────────────────────────────────────

/**
 * One metric: label, value, and a sub-line that carries its qualifier.
 *
 * `sub` is where the sample size, the window or the "не настроено" note lives —
 * in the same visual unit as the value, never as a tooltip.
 */
export function metric({ label, value, sub, tone, large = false, stale = false, title }) {
  const classes = [
    large ? 'qf-metric-value qf-metric-value--lg' : 'qf-metric-value',
    tone || '',
    stale ? 'qf-value--stale' : '',
    'qf-num',
  ].filter(Boolean).join(' ');

  return el('div', { className: 'qf-metric-cell' }, [
    el('div', { className: 'qf-metric-label', text: label, title: title || label }),
    el('div', { className: classes, text: value, title }),
    sub ? el('div', { className: 'qf-metric-sub', text: sub }) : null,
  ]);
}

export function metricsGrid(cells) {
  return el('div', { className: 'qf-metrics' }, cells.filter(Boolean));
}

/**
 * A money metric that renders `н/д` rather than `0,00 ₽` when unmeasured.
 *
 * Three tiles reading `+0,00 ₽` were the old Overview's first fold, and a measured
 * zero was indistinguishable from an absent measurement.
 */
export function moneyMetric({ label, value, n, currency = 'RUB', signed = true, window: windowLabel, large, stale }) {
  const measured = fmt.isNumber(value) && (n === undefined || n > 0);
  const parts = [];
  if (windowLabel) parts.push(windowLabel);
  if (n !== undefined) parts.push(fmt.sampleSuffix(n));
  return metric({
    label,
    value: measured ? fmt.money(value, { currency, signed }) : fmt.NO_DATA,
    sub: parts.join(` ${fmt.MIDDOT} `) || undefined,
    tone: measured ? fmt.signClass(value) : 'qf-unknown-value',
    large,
    stale,
  });
}

export function percentMetric({ label, value, n, window: windowLabel, signed = true, large, stale }) {
  const measured = fmt.isNumber(value) && (n === undefined || n > 0);
  const parts = [];
  if (windowLabel) parts.push(windowLabel);
  if (n !== undefined) parts.push(fmt.sampleSuffix(n));
  return metric({
    label,
    value: measured ? fmt.percent(value, { signed }) : fmt.NO_DATA,
    sub: parts.join(` ${fmt.MIDDOT} `) || undefined,
    tone: measured ? fmt.signClass(value) : 'qf-unknown-value',
    large,
    stale,
  });
}

/** A limit that is either configured or explicitly not. Never rendered as 0. */
export function limitMetric({ label, limit, current, format = fmt.number }) {
  if (!limit || !limit.configured) {
    return metric({
      label,
      value: t('risk.not_configured'),
      tone: 'qf-unknown-value',
      sub: limit && limit.source ? limit.source : undefined,
    });
  }
  return metric({
    label,
    value: fmt.isNumber(current) ? `${format(current)} / ${format(limit.value)}` : format(limit.value),
    sub: limit.source,
  });
}

// ── Status ───────────────────────────────────────────────────────────────────

/**
 * A status: shaped dot plus its word.
 *
 * The word is mandatory and comes from the server, so the eight states survive
 * greyscale and colour-blindness. `shape` differs per state for the same reason.
 */
export function status({ state, label, shape, title }) {
  return el('span', {
    className: 'qf-status',
    dataset: { state: state || 'unknown' },
    title,
  }, [
    el('span', { className: 'qf-status-shape', dataset: { shape: shape || 'dot-filled' } }),
    el('span', { className: 'qf-status-word', text: label || state || 'неизвестно' }),
  ]);
}

/** A small chip: gate decision, environment, sample maturity. */
export function chip(label, { tone, env, title } = {}) {
  return el('span', {
    className: env ? 'qf-chip qf-chip--env' : 'qf-chip',
    dataset: { tone, env },
    text: label,
    title,
  });
}

/** Row-level environment marker. Present wherever a row has an environment. */
export function environmentChip(environment) {
  const labels = {
    sandbox: 'песочница', forward: 'форвард', backtest: 'бэктест',
    live: 'LIVE', unknown: 'неизвестно',
  };
  const value = environment || 'unknown';
  return chip(labels[value] || value, {
    env: value,
    title: value === 'unknown'
      ? 'Происхождение строки не определено — это ошибка конфигурации.'
      : undefined,
  });
}

/**
 * Confidence — always with its sample size, and marked when immature.
 *
 * There is no code path in this module that renders a confidence without its `n`.
 */
export function confidenceValue(value, sampleSize, { mature } = {}) {
  const isMature = mature ?? (sampleSize >= 30);
  return el('span', { className: 'qf-num' }, [
    el('span', {
      className: isMature ? '' : 'qf-unknown-value',
      text: fmt.confidence(value, sampleSize),
      title: t('strategies.confidence_note'),
    }),
    isMature ? null : chip(t('strategies.immature'), { tone: 'neutral' }),
  ]);
}

/** A stale marker for one cell, with the absolute time on hover. */
export function staleMark(ageSeconds, absolute) {
  return el('span', {
    className: 'qf-stale',
    text: fmt.age(ageSeconds),
    title: absolute ? `${t('common.source')}: ${absolute}` : undefined,
  });
}

// ── Data states ──────────────────────────────────────────────────────────────

/**
 * The one function that turns a slice snapshot into a rendered state.
 *
 * Returns `null` when the region should render its data instead. Every branch
 * produces a *different* message and, where applicable, an action — collapsing
 * them is how «у меня всё нулями» becomes an unreported outage.
 */
export function stateFor(snapshot, { onRetry, skeleton, emptyExtra } = {}) {
  if (!snapshot) return loadingState(skeleton);

  switch (snapshot.state) {
    case SliceState.IDLE:
    case SliceState.LOADING:
      return loadingState(skeleton);

    case SliceState.REFRESHING:
      // Previous data stays visible; the panel's aria-busy hairline is the only
      // signal. Never blank a populated panel.
      return snapshot.hasData ? null : loadingState(skeleton);

    case SliceState.EMPTY:
      return el('div', { className: 'qf-state' }, [
        emptyFigure(),
        el('div', {
          className: 'qf-state-title',
          text: emptyReasonText(snapshot.meta && snapshot.meta.empty_reason),
        }),
        emptyExtra ? el('div', { className: 'qf-state-detail', text: emptyExtra }) : null,
      ]);

    case SliceState.FORBIDDEN:
      return el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.error.FORBIDDEN') }),
        el('div', {
          className: 'qf-state-detail',
          text: (snapshot.error && snapshot.error.message) || 'Права выдаёт администратор.',
        }),
      ]);

    case SliceState.DISCONNECTED:
      return errorState({
        title: t('state.disconnected'),
        detail: 'Данные ниже заморожены на момент последнего успешного обновления.',
        error: snapshot.error,
        onRetry,
        // Keep the stale data on screen rather than clearing it.
        overlay: snapshot.hasData,
      });

    case SliceState.ERROR:
      return errorState({
        title: errorText(snapshot.error && snapshot.error.code),
        detail: snapshot.error && snapshot.error.message,
        error: snapshot.error,
        onRetry,
        overlay: snapshot.hasData,
      });

    case SliceState.STALE:
    case SliceState.PARTIAL:
    case SliceState.LOADED:
    default:
      // Stale and partial render their data — marked, not hidden. Hiding a stale
      // number is worse than showing it labelled, because the operator then has
      // no number at all and no explanation.
      return null;
  }
}

function loadingState(skeleton) {
  if (skeleton === false) {
    return el('div', { className: 'qf-state' }, [
      el('div', { className: 'qf-state-title', text: t('state.loading') }),
    ]);
  }
  const rows = typeof skeleton === 'number' ? skeleton : 3;
  return el('div', { className: 'qf-panel-body' }, Array.from({ length: rows }, () =>
    el('div', {
      className: 'qf-skeleton',
      // Skeletons match the final layout's dimensions, so the panel does not
      // resize when real content replaces them.
      style: { height: '20px', width: '100%' },
      attrs: { 'aria-hidden': 'true' },
    })));
}

export function errorState({ title, detail, error, onRetry, overlay = false }) {
  return el('div', {
    className: overlay ? 'qf-state' : 'qf-state qf-state--error',
    // A failure is announced, not just drawn. Nothing was announced before:
    // errors were console.warn only.
    attrs: { role: 'alert' },
  }, [
    el('div', { className: 'qf-state-title', text: title }),
    detail ? el('div', { className: 'qf-state-detail', text: detail }) : null,
    error && error.correlationId
      ? el('div', {
        className: 'qf-state-id',
        text: `${t('state.error_id')}: ${error.correlationId}`,
      })
      : null,
    onRetry
      ? el('button', {
        className: 'qf-btn',
        text: t('state.retry'),
        attrs: { type: 'button' },
        on: { click: onRetry },
      })
      : null,
  ]);
}

/** Empty-state geometry: the one place cold blue is permitted, as a stroke. */
function emptyFigure() {
  return svg('svg', {
    class: 'qf-state-figure',
    viewBox: '0 0 48 48',
    'aria-hidden': 'true',
    focusable: 'false',
  }, [
    svg('circle', { cx: '24', cy: '24', r: '18' }),
    svg('path', { d: 'M12 30 L20 22 L26 27 L36 16' }),
  ]);
}

/** A partial-data note, naming what did not arrive. */
export function partialNote(missing) {
  const names = Object.keys(missing || {});
  if (!names.length) return null;
  return el('div', {
    className: 'qf-state-detail',
    attrs: { role: 'status' },
    text: `${t('state.partial')}: ${names.join(', ')}`,
  });
}

// ── Toasts ───────────────────────────────────────────────────────────────────

class Toasts {
  constructor() {
    this.root = null;
  }

  mount(root) {
    this.root = root;
    // `aria-live="polite"` so a result is announced without interrupting.
    root.setAttribute('role', 'status');
    root.setAttribute('aria-live', 'polite');
    root.setAttribute('aria-atomic', 'false');
  }

  show(message, { tone = 'info', duration = 6000, detail } = {}) {
    if (!this.root) return () => {};
    const node = el('div', { className: 'qf-toast', dataset: { tone } }, [
      el('div', {}, [
        el('div', { text: message }),
        detail ? el('div', { className: 'qf-state-id', text: detail }) : null,
      ]),
      el('button', {
        className: 'qf-btn qf-btn--ghost qf-btn--icon',
        text: '✕',
        attrs: { type: 'button', 'aria-label': 'Закрыть' },
        on: { click: () => node.remove() },
      }),
    ]);
    this.root.appendChild(node);
    // Errors persist until dismissed: a failure that vanishes after six seconds
    // is a failure the operator may never have seen.
    if (tone !== 'error' && duration > 0) {
      window.setTimeout(() => node.remove(), duration);
    }
    return () => node.remove();
  }

  success(message, detail) { return this.show(message, { tone: 'success', detail }); }
  error(message, detail) { return this.show(message, { tone: 'error', detail, duration: 0 }); }
  info(message, detail) { return this.show(message, { tone: 'info', detail }); }
}

export const toasts = new Toasts();

/** A polite live region for table-cell announcements and status changes. */
export function mountAnnouncer(node) {
  node.setAttribute('role', 'status');
  node.setAttribute('aria-live', 'polite');
  window.addEventListener('qf:announce', (event) => {
    node.textContent = event.detail && event.detail.message ? event.detail.message : '';
  });
}

// ── Dialogs ──────────────────────────────────────────────────────────────────

/**
 * The confirmation gate for a mutation.
 *
 * Four things the old controls all lacked: a confirmation naming the effect, a
 * disabled state while in flight, a typed confirmation for anything that moves
 * money, and a reason field whose value is stored in the audit row.
 *
 * @param {object} config
 *   title, body, confirmLabel, danger
 *   typedConfirmation: the exact string the operator must type (ticker, key name)
 *   requireReason: boolean
 *   onConfirm({ reason }) → Promise
 */
export function confirmDialog(config) {
  return new Promise((resolve) => {
    const {
      title, body, confirmLabel = t('action.confirm'), danger = false,
      typedConfirmation = null, requireReason = false,
    } = config;

    let releaseFocus = null;
    let inFlight = false;

    const errorNode = el('div', { className: 'qf-field-error', attrs: { role: 'alert' } });
    const reasonInput = el('input', {
      className: 'qf-input',
      attrs: { type: 'text', id: 'qf-dialog-reason', maxlength: '500' },
    });
    const confirmInput = el('input', {
      className: 'qf-input qf-mono',
      attrs: { type: 'text', id: 'qf-dialog-confirm', autocomplete: 'off', spellcheck: 'false' },
    });

    const confirmButton = el('button', {
      className: danger ? 'qf-btn qf-btn--danger' : 'qf-btn qf-btn--primary',
      text: confirmLabel,
      attrs: { type: 'submit' },
    });

    function close(result) {
      if (releaseFocus) releaseFocus();
      scrim.remove();
      dialog.remove();
      document.removeEventListener('keydown', onEscape);
      resolve(result);
    }

    function onEscape(event) {
      if (event.key === 'Escape' && !inFlight) close({ confirmed: false });
    }

    async function submit(event) {
      event.preventDefault();
      if (inFlight) return;

      errorNode.textContent = '';
      if (typedConfirmation && confirmInput.value.trim() !== typedConfirmation) {
        errorNode.textContent = `${t('action.type_to_confirm')} «${typedConfirmation}».`;
        confirmInput.focus();
        return;
      }
      const reason = reasonInput.value.trim();
      if (requireReason && !reason) {
        errorNode.textContent = t('action.reason_required');
        reasonInput.focus();
        return;
      }

      // Disabled while in flight — a double click used to issue two POSTs.
      inFlight = true;
      confirmButton.disabled = true;
      confirmButton.setAttribute('aria-busy', 'true');
      confirmButton.textContent = t('action.in_flight');

      try {
        const outcome = await config.onConfirm({ reason });
        close({ confirmed: true, outcome });
      } catch (error) {
        inFlight = false;
        confirmButton.disabled = false;
        confirmButton.removeAttribute('aria-busy');
        confirmButton.textContent = confirmLabel;
        // The dialog stays open on failure and states what happened, so the
        // operator is not left guessing whether the action took effect.
        errorNode.textContent = error && error.message ? error.message : t('action.failed');
        if (error && error.correlationId) {
          errorNode.textContent += ` (${t('state.error_id')}: ${error.correlationId})`;
        }
      }
    }

    const form = el('form', { on: { submit } }, [
      el('h2', { className: 'qf-dialog-title', text: title, attrs: { id: 'qf-dialog-title' } }),
      el('div', { className: 'qf-dialog-body' }, [
        typeof body === 'string' ? el('p', { text: body }) : body,
        typedConfirmation
          ? el('div', { className: 'qf-field' }, [
            el('label', {
              className: 'qf-field-label',
              text: `${t('action.type_to_confirm')} «${typedConfirmation}»`,
              attrs: { for: 'qf-dialog-confirm' },
            }),
            confirmInput,
          ])
          : null,
        requireReason
          ? el('div', { className: 'qf-field' }, [
            el('label', {
              className: 'qf-field-label',
              text: t('action.reason'),
              attrs: { for: 'qf-dialog-reason' },
            }),
            reasonInput,
            el('div', { className: 'qf-state-detail', text: t('action.reason_required') }),
          ])
          : null,
        errorNode,
      ]),
      el('div', { className: 'qf-dialog-actions' }, [
        el('button', {
          className: 'qf-btn',
          text: t('action.cancel'),
          attrs: { type: 'button' },
          on: { click: () => { if (!inFlight) close({ confirmed: false }); } },
        }),
        confirmButton,
      ]),
    ]);

    const scrim = el('div', { className: 'qf-scrim' });
    const dialogPanel = el('div', { className: 'qf-dialog-panel' }, [form]);
    const dialog = el('div', {
      className: 'qf-dialog',
      attrs: {
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': 'qf-dialog-title',
      },
    }, [dialogPanel]);

    document.body.append(scrim, dialog);
    releaseFocus = trapFocus(dialogPanel);
    document.addEventListener('keydown', onEscape);
  });
}

/**
 * A disabled action button that explains itself.
 *
 * `opacity: 0.45` was the entire disabled state — it failed contrast and was
 * indistinguishable from "loading". A disabled trading control must state *why*.
 */
export function actionButton({ label, onClick, permitted, reason, danger = false, primary = false }) {
  const classes = ['qf-btn'];
  if (danger) classes.push('qf-btn--danger');
  else if (primary) classes.push('qf-btn--primary');

  const button = el('button', {
    className: classes.join(' '),
    text: label,
    attrs: {
      type: 'button',
      disabled: !permitted,
      title: permitted ? undefined : reason,
      'aria-description': permitted ? undefined : reason,
    },
  });
  if (permitted) button.addEventListener('click', onClick);
  return button;
}

/** A chart panel: the chart, its textual summary, and a data-table toggle. */
export function chartPanel({ title, meta, height = '200px', summary, tableRows, tableColumns }) {
  const built = panel({ title, flush: true, chartHeight: height });
  const chartHost = el('div', { className: 'qf-chart' });
  const summaryNode = el('p', { className: 'qf-chart-summary', text: summary || '' });
  const tableHost = el('div', { attrs: { hidden: true } });

  const toggle = el('button', {
    className: 'qf-btn qf-btn--ghost',
    text: t('analytics.data_table'),
    attrs: { type: 'button', 'aria-expanded': 'false' },
  });
  toggle.addEventListener('click', () => {
    const showing = !tableHost.hidden;
    tableHost.hidden = showing;
    chartHost.hidden = !showing;
    toggle.textContent = showing ? t('analytics.data_table') : t('analytics.chart');
    toggle.setAttribute('aria-expanded', showing ? 'false' : 'true');
  });

  append(built.meta, toggle);
  if (meta) append(built.meta, el('span', { text: meta }));
  render(built.body, [chartHost, summaryNode, tableHost]);

  return { ...built, chartHost, summaryNode, tableHost, toggle, tableRows, tableColumns };
}
