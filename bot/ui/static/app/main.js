/**
 * Application entry point.
 *
 * Wires the shell: environment band, fault region, router, sync registrations,
 * views, actions, shortcuts. One module owns each region, and a view's mount
 * returns its own teardown — so switching views cannot leave a listener, an
 * interval, a chart or a subscription behind.
 */

import { ApiError, abortAll, api, newIdempotencyKey } from './api.js';
import { ChartRegistry } from './charts.js';
import { append, byId, el, icon, maybeById, render } from './dom.js';
import * as fmt from './format.js';
import { t } from './i18n.js';
import { Router, Shortcuts } from './router.js';
import { Cadence, EventStream, sync } from './sync.js';
import { SliceState, store } from './store.js';
import {
  actionButton, confirmDialog, mountAnnouncer, status, toasts,
} from './ui.js';
import { createOverview } from './views/overview.js';
import {
  createAnalytics, createBacktest, createEvents, createHealth, createPortfolio,
  createPositions, createRisk, createSettings, createSignals, createStrategies,
  createTrades,
} from './views/screens.js';

// ── Navigation model ─────────────────────────────────────────────────────────
// A section exists only when there is a working endpoint and a real interface
// behind it. Orders and Notifications are absent because no entity exists for
// them; Quant Hunter is absent because it is a game and now lives at /miniapp.

const NAV = [
  { group: t('nav.group.trading'), items: [
    { id: 'overview', label: t('nav.overview'), path: '/', icon: 'M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z' },
    { id: 'portfolio', label: t('nav.portfolio'), path: '/portfolio', icon: 'M3 12h3v6H3zM8.5 8h3v10h-3zM14 4h3v14h-3z' },
    { id: 'positions', label: t('nav.positions'), path: '/positions', icon: 'M3 6h14M3 10h14M3 14h9' },
    { id: 'trades', label: t('nav.trades'), path: '/trades', icon: 'M3 14l4-5 3 3 6-7M13 5h4v4' },
    { id: 'signals', label: t('nav.signals'), path: '/signals', icon: 'M11 2L4 11h5l-1 7 7-10h-5z' },
    { id: 'strategies', label: t('nav.strategies'), path: '/strategies', icon: 'M4 16V8M8 16V4M12 16v-5M16 16V9' },
    { id: 'backtest', label: t('nav.backtest'), path: '/backtest', icon: 'M4 10H2l2-3 2 3H4m0 4h8a4 4 0 100-8H6' },
    { id: 'analytics', label: t('nav.analytics'), path: '/analytics', icon: 'M3 17l4-6 4 4 3-5 3 6M3 3v14h14' },
    { id: 'risk', label: t('nav.risk'), path: '/risk', icon: 'M10 3l7 13H3zM10 8v4M10 14h.01' },
  ] },
  { group: t('nav.group.system'), items: [
    // `/status`, not `/health`: GET /health is the liveness probe.
    { id: 'health', label: t('nav.health'), path: '/status', icon: 'M3 10h3l2-4 3 8 2-4h4' },
    { id: 'events', label: t('nav.events'), path: '/events', icon: 'M5 4h10v12H5zM8 8h4M8 11h4' },
    { id: 'settings', label: t('nav.settings'), path: '/settings', icon: 'M10 7.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5M10 2v2M10 16v2M2 10h2M16 10h2M4.5 4.5l1.4 1.4M14.1 14.1l1.4 1.4M15.5 4.5l-1.4 1.4M5.9 14.1l-1.4 1.4' },
  ] },
];

const VIEW_FACTORIES = {
  overview: createOverview,
  portfolio: createPortfolio,
  positions: createPositions,
  trades: createTrades,
  signals: createSignals,
  strategies: createStrategies,
  backtest: createBacktest,
  analytics: createAnalytics,
  risk: createRisk,
  health: createHealth,
  events: createEvents,
  settings: createSettings,
};

/** Which slices each view needs — drives whether a task polls at all. */
const VIEW_SLICES = {
  overview: ['overview'],
  portfolio: ['portfolio'],
  positions: ['positions'],
  trades: ['trades'],
  signals: ['signals'],
  strategies: ['strategies'],
  backtest: [],
  analytics: ['equity', 'underwater', 'dailyPnl', 'distribution'],
  risk: ['risk', 'riskEvents'],
  health: ['health'],
  events: ['events'],
  settings: ['credentials', 'risk'],
};

// ── Session ──────────────────────────────────────────────────────────────────

class Session {
  constructor() {
    this.user = null;
    this.readOnly = false;
    this.permissions = new Set();
  }

  apply(payload) {
    this.user = payload.user || null;
    this.readOnly = Boolean(payload.read_only);
    this.permissions = new Set((this.user && this.user.permissions) || []);
  }

  can(permission) {
    // Read-only mode removes every mutating capability, so a control is disabled
    // with a reason rather than failing at the server.
    if (this.readOnly && permission !== 'view' && permission !== 'view_audit') return false;
    return this.permissions.has(permission);
  }

  denialReason(permission) {
    if (this.readOnly) return t('band.readonly') + ' — изменения недоступны.';
    if (!this.user) return t('state.error.FORBIDDEN');
    return `Недостаточно прав: требуется «${permission}». Права выдаёт администратор.`;
  }
}

// ── Application ──────────────────────────────────────────────────────────────

class App {
  constructor() {
    this.session = new Session();
    this.charts = new ChartRegistry();
    this.shortcuts = new Shortcuts();
    this.stream = new EventStream();
    this.views = new Map();
    this.activeView = null;
    this.activeTeardown = null;
    this.paramListeners = new Set();
    this.density = window.localStorage.getItem('qf.density') || 'comfortable';

    this.routes = Object.fromEntries(
      NAV.flatMap((group) => group.items).map((item) => [
        item.id, { path: item.path, title: item.label },
      ]),
    );
    this.router = new Router(this.routes, { defaultRoute: 'overview' });
  }

  // ── Boot ───────────────────────────────────────────────────────────────────

  async start() {
    this.appRoot = byId('qf-app');
    this.contentRoot = byId('qf-content');
    this.bandRoot = byId('qf-band');
    this.faultsRoot = byId('qf-faults');
    this.navRoot = byId('qf-nav');
    this.titleRoot = byId('qf-view-title');
    this.contextRoot = byId('qf-view-context');
    this.clockRoot = byId('qf-clock');
    this.statusRoot = byId('qf-sync-status');
    this.userRoot = byId('qf-user');

    toasts.mount(byId('qf-toasts'));
    mountAnnouncer(byId('qf-announcer'));

    // Surface a broken listener rather than letting it vanish into console.warn.
    window.addEventListener('qf:listener-error', (event) => {
      toasts.error('Ошибка отрисовки панели', event.detail && event.detail.slice);
    });
    window.addEventListener('qf:unauthenticated', () => this.handleSessionLoss());

    let sessionPayload;
    try {
      const { data } = await api.session();
      sessionPayload = data;
    } catch {
      window.location.assign('/login');
      return;
    }
    if (!sessionPayload.authenticated) {
      window.location.assign('/login');
      return;
    }
    this.session.apply(sessionPayload);

    this.renderNav();
    this.renderUser();
    this.startClock();
    this.registerSlices();
    this.bindShortcuts();
    this.bindShellControls();

    store.subscribe('overview', (snapshot) => this.renderBand(snapshot));
    store.subscribe('overview', (snapshot) => this.renderFaults(snapshot));
    store.subscribeGlobal((status) => this.renderSyncStatus(status));

    this.router.onChange((snapshot) => this.onRoute(snapshot));
    this.router.start();
    this.shortcuts.start();
    sync.start();

    // SSE is a hint to refresh, not a data channel — see sync.js.
    this.stream.on('trade_executed', () => sync.refresh('positions'));
    this.stream.on('portfolio_updated', () => sync.refresh('overview'));
    this.stream.on('signals_updated', () => sync.refresh('signals'));
    this.stream.on('signal_rejected', () => sync.refresh('signals'));
    this.stream.connect();

    window.addEventListener('beforeunload', () => this.dispose());
    document.documentElement.dataset.density = this.density;
  }

  dispose() {
    sync.stop();
    this.shortcuts.stop();
    this.router.stop();
    this.stream.dispose();
    if (this.activeTeardown) this.activeTeardown();
    for (const view of this.views.values()) view.dispose();
    this.charts.destroyAll();
    if (this.clockTimer) window.clearInterval(this.clockTimer);
  }

  // ── Sync registrations ─────────────────────────────────────────────────────

  registerSlices() {
    const needs = (slice) => () => {
      const current = this.router.current;
      return Boolean(current && (VIEW_SLICES[current] || []).includes(slice));
    };
    const params = () => this.router.params();

    // The Overview is one composed request, always polled: the environment band
    // and the fault region are shell furniture, visible on every screen.
    //
    // There is deliberately no separate `faults` task. /api/v2/overview already
    // carries the fault region, so polling /api/v2/faults as well would double the
    // shell's request rate to buy nothing — and the two answers could disagree by
    // one interval, which is exactly the kind of self-contradiction the old
    // dashboard shipped. `renderFaults` reads the overview slice instead.
    sync.register({
      name: 'overview', interval: Cadence.FAST,
      fetcher: () => api.overview({ environment: params().environment }),
    });

    const slices = [
      ['positions', () => api.positions({ environment: params().environment }), Cadence.NORMAL,
        (data) => !data || !data.positions || data.positions.length === 0],
      ['trades', () => api.trades({
        period: params().period || '30d', environment: params().environment,
        ticker: params().ticker, direction: params().direction, result: params().result,
        sort: params().sort,
      }), Cadence.SLOW, (data) => !data || data.total === 0],
      ['signals', () => api.signals({
        environment: params().environment, decision: params().decision, ticker: params().ticker,
      }), Cadence.NORMAL, (data) => !data || data.count === 0],
      ['strategies', () => api.strategies({ environment: params().environment }), Cadence.SLOW,
        (data) => !data || data.count === 0],
      ['portfolio', () => api.portfolio({
        period: params().period || '30d', environment: params().environment,
      }), Cadence.SLOW],
      ['risk', () => api.risk({ environment: params().environment, window: params().window }), Cadence.NORMAL],
      ['riskEvents', () => api.riskEvents(), Cadence.LAZY, (data) => !data || data.count === 0],
      ['equity', () => api.equity({
        window: params().window || '90d', environment: params().environment,
      }), Cadence.SLOW, (data) => !data || !data.points || data.points.length === 0],
      ['underwater', () => api.underwater({ window: params().window || '90d' }), Cadence.SLOW,
        (data) => !data || !data.points || data.points.length === 0],
      ['dailyPnl', () => api.dailyPnl({ environment: params().environment }), Cadence.SLOW,
        (data) => !data || !data.points || data.points.length === 0],
      ['distribution', () => api.distribution({ period: params().period || 'all' }), Cadence.SLOW,
        (data) => !data || !data.bins || data.bins.length === 0],
      ['health', () => api.health(), Cadence.NORMAL],
      ['events', () => api.events({
        level: params().level, q: params().q, correlation_id: params().correlation_id,
      }), Cadence.LAZY, (data) => !data || data.count === 0],
      ['credentials', () => api.credentials(), Cadence.LAZY],
    ];

    for (const [name, fetcher, interval, isEmpty] of slices) {
      sync.register({ name, fetcher, interval, isEmpty, enabled: needs(name) });
    }
  }

  // ── Shell rendering ────────────────────────────────────────────────────────

  renderNav() {
    const groups = NAV.map((group) => el('div', {}, [
      el('div', { className: 'qf-nav-group qf-nav-label', text: group.group }),
      ...group.items.map((item) => {
        const link = el('a', {
          className: 'qf-nav-item',
          attrs: { href: item.path, 'data-nav': item.id },
        }, [
          icon(item.icon),
          el('span', { className: 'qf-nav-label', text: item.label }),
        ]);
        link.addEventListener('click', (event) => {
          // Intercept only a plain left click, so ⌘-click still opens a new tab.
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
          event.preventDefault();
          this.router.navigate(item.id);
        });
        return link;
      }),
    ]));
    render(this.navRoot, groups);
  }

  renderUser() {
    const user = this.session.user || {};
    render(this.userRoot, [
      el('div', { className: 'qf-user-avatar', text: (user.display_name || 'ᴏ').charAt(0).toUpperCase() }),
      el('div', { className: 'qf-user-meta qf-sidebar-footer-text' }, [
        el('div', { className: 'qf-user-name', text: user.display_name || user.username || '' }),
        el('div', { className: 'qf-user-role', text: user.role_label || '' }),
      ]),
    ]);
  }

  startClock() {
    const tick = () => {
      this.clockRoot.textContent = `${fmt.clockTime(new Date())} MSK`;
    };
    tick();
    // A ticking clock is honest liveness: a value that visibly changes reads as
    // motion without being decoration, which is what the pulsing dots faked.
    this.clockTimer = window.setInterval(tick, 1000);
  }

  renderBand(snapshot) {
    const environment = snapshot.hasData && snapshot.data.environment;
    if (!environment) {
      // No environment resolved yet — say so rather than assuming sandbox.
      this.bandRoot.className = 'qf-band qf-band--unknown';
      render(this.bandRoot, [
        el('span', { className: 'qf-band-env', text: 'СРЕДА НЕ ОПРЕДЕЛЕНА' }),
      ]);
      return;
    }

    const isLive = environment.environment === 'live';
    const isUnknown = environment.environment === 'unknown' || environment.is_environment_fault;
    this.bandRoot.className = `qf-band${isLive ? ' qf-band--live' : ''}${isUnknown ? ' qf-band--unknown' : ''}`;

    const marketData = environment.market_data || {};
    const engine = environment.engine || {};
    const parts = [
      el('span', { className: 'qf-band-env', text: environment.environment_label }),
      el('span', { className: 'qf-band-sep', text: fmt.MIDDOT }),
      el('span', { text: environment.broker }),
      el('span', { className: 'qf-band-sep', text: fmt.MIDDOT }),
      el('span', { text: `${t('band.engine')}: ${engine.label || fmt.NO_DATA}` }),
      el('span', { className: 'qf-band-sep', text: fmt.MIDDOT }),
      el('span', { text: `${t('band.data')}: ` }),
      marketData.is_stale
        ? el('span', {
          className: 'qf-stale',
          text: fmt.ageAgo(marketData.data_age_seconds),
          title: marketData.source_as_of ? fmt.absoluteTime(marketData.source_as_of) : undefined,
        })
        : el('span', {
          text: marketData.data_age_seconds === null || marketData.data_age_seconds === undefined
            ? 'возраст неизвестен' : fmt.ageAgo(marketData.data_age_seconds),
          title: marketData.source_as_of ? fmt.absoluteTime(marketData.source_as_of) : undefined,
        }),
    ];

    if (environment.read_only) {
      parts.push(el('span', { className: 'qf-band-sep', text: fmt.MIDDOT }));
      parts.push(el('span', { className: 'qf-chip', text: t('band.readonly') }));
    }
    if (!environment.trading_actions_enabled) {
      parts.push(el('span', { className: 'qf-chip', text: t('band.trading_disabled') }));
    }

    // Engine control lives in the band: it is where engine state is read, so it
    // is where the action belongs.
    const running = engine.state === 'running';
    parts.push(el('span', { style: { 'margin-left': 'auto' } }));
    parts.push(actionButton({
      label: running ? t('action.engine_stop') : t('action.engine_start'),
      danger: running,
      permitted: this.session.can('engine_control'),
      reason: this.session.denialReason('engine_control'),
      onClick: () => (running ? this.stopEngine() : this.startEngine()),
    }));

    // `role="status"` so the band's changes are announced; it never moves or
    // animates, so announcement is the only signal a non-visual user gets.
    this.bandRoot.setAttribute('role', 'status');
    this.bandRoot.setAttribute('aria-live', 'polite');
    render(this.bandRoot, parts);
  }

  renderFaults(snapshot) {
    // Reads the composed overview payload's `faults` slice — one request serves
    // the band and the fault region.
    const payload = snapshot.hasData ? snapshot.data.faults : null;
    if (!payload || !payload.faults || !payload.faults.length) {
      // Zero rows, zero height. No permanent green "all clear".
      render(this.faultsRoot, null);
      return;
    }
    const rows = payload.faults.map((fault) => el('div', {
      className: 'qf-fault',
      attrs: { role: fault.severity >= 3 ? 'alert' : 'status' },
    }, [
      status({ state: fault.state, label: fault.label, shape: fault.shape }),
      el('span', { className: 'qf-fault-subject', text: fault.subject }),
      el('span', { className: 'qf-fault-reason', text: fault.reason }),
      el('span', { className: 'qf-fault-time',
        text: fault.occurred_at ? fmt.smartTime(fault.occurred_at) : '' }),
      fault.action && fault.action.route
        ? el('button', {
          className: 'qf-btn qf-btn--ghost',
          text: fault.action.label,
          attrs: { type: 'button', title: fault.action.hint || undefined },
          on: { click: () => this.navigateToPath(fault.action.route) },
        })
        : null,
      actionButton({
        label: t('action.acknowledge'),
        permitted: this.session.can('acknowledge_fault'),
        reason: this.session.denialReason('acknowledge_fault'),
        onClick: () => this.acknowledge(fault.code),
      }),
    ]));

    if (payload.hidden > 0) {
      rows.push(el('div', { className: 'qf-fault' }, [
        el('span', { className: 'qf-fault-reason', text: `+${fmt.integer(payload.hidden)} ещё` }),
        el('button', {
          className: 'qf-btn qf-btn--ghost', text: t('nav.health'), attrs: { type: 'button' },
          on: { click: () => this.router.navigate('health') },
        }),
      ]));
    }
    render(this.faultsRoot, rows);
  }

  /**
   * The sync indicator. Never claims "live" unless every tracked slice agrees.
   *
   * The old client set `syncStatus: 'live'` unconditionally after
   * `Promise.allSettled` and stamped a fresh timestamp with a green dot over a
   * screen that was 32 days old.
   */
  renderSyncStatus(globalStatus) {
    const map = {
      [SliceState.LOADED]: { state: 'healthy', label: 'Данные актуальны', shape: 'dot-filled' },
      [SliceState.EMPTY]: { state: 'healthy', label: 'Данные актуальны', shape: 'dot-filled' },
      [SliceState.LOADING]: { state: 'unknown', label: t('state.loading'), shape: 'ring-dashed' },
      [SliceState.REFRESHING]: { state: 'unknown', label: 'Обновление…', shape: 'ring-dashed' },
      [SliceState.IDLE]: { state: 'unknown', label: t('shell.never_updated'), shape: 'ring-dashed' },
      [SliceState.PARTIAL]: { state: 'degraded', label: t('state.partial'), shape: 'dot-half' },
      [SliceState.STALE]: { state: 'stale', label: t('state.stale'), shape: 'ring' },
      [SliceState.FORBIDDEN]: { state: 'stale', label: t('state.error.FORBIDDEN'), shape: 'ring' },
      [SliceState.DISCONNECTED]: { state: 'disconnected', label: t('state.disconnected'), shape: 'ring' },
      [SliceState.ERROR]: { state: 'failed', label: t('state.error'), shape: 'dot-filled' },
    };
    const view = map[globalStatus.state] || map[SliceState.IDLE];
    const detail = [];
    if (globalStatus.worstSlice) detail.push(globalStatus.worstSlice);
    if (globalStatus.lastUpdatedAt) {
      detail.push(`${t('shell.updated')} ${fmt.clockTime(new Date(globalStatus.lastUpdatedAt))}`);
    }
    if (fmt.isNumber(globalStatus.oldestSourceAgeSeconds)) {
      detail.push(`источник: ${fmt.age(globalStatus.oldestSourceAgeSeconds)}`);
    }
    render(this.statusRoot, [status({ ...view, title: detail.join(' · ') })]);
  }

  // ── Routing ────────────────────────────────────────────────────────────────

  navigateToPath(path) {
    const entry = Object.entries(this.routes).find(([, route]) => route.path === path);
    if (entry) this.router.navigate(entry[0]);
  }

  onRoute({ id, changed }) {
    for (const link of this.navRoot.querySelectorAll('[data-nav]')) {
      if (link.dataset.nav === id) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    const route = this.routes[id];
    this.titleRoot.textContent = route ? route.title : '';
    this.contextRoot.textContent = 'Терминал оператора';

    if (!changed) {
      // Same view, different filters. Notify the view rather than remounting it,
      // so a filter change does not rebuild the DOM or lose scroll position.
      for (const listener of this.paramListeners) listener();
      sync.refresh();
      return;
    }
    this.mountView(id);
  }

  mountView(id) {
    // Cancel the previous view's in-flight requests: a slow response from the
    // screen the operator just left must not overwrite the one they are on.
    abortAll();
    if (this.activeTeardown) {
      this.activeTeardown();
      this.activeTeardown = null;
    }

    let view = this.views.get(id);
    if (!view) {
      const factory = VIEW_FACTORIES[id];
      if (!factory) return;
      view = factory(this.context());
      this.views.set(id, view);
    }

    render(this.contentRoot, view.root);
    view.root.classList.add('qf-fade-in');
    view.root.dataset.active = 'true';
    this.activeView = id;
    this.activeTeardown = view.mount() || (() => {});
    // Refresh this view's slices immediately rather than waiting a full interval.
    for (const slice of VIEW_SLICES[id] || []) sync.refresh(slice);
    this.contentRoot.focus({ preventScroll: true });
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  async startEngine() {
    const result = await confirmDialog({
      title: t('action.engine_start'),
      body: 'Движок начнёт генерировать сигналы и открывать сделки в песочнице.',
      confirmLabel: t('action.engine_start'),
      onConfirm: () => api.engineStart(''),
    });
    if (result.confirmed) {
      toasts.success(t('action.succeeded'));
      sync.refresh('overview');
    }
  }

  async stopEngine() {
    // Stopping requires a reason; starting does not. An engine that is off needs
    // an explanation the next operator can read.
    const result = await confirmDialog({
      title: t('action.engine_stop'),
      body: 'Движок перестанет открывать новые сделки. Открытые позиции останутся.',
      confirmLabel: t('action.engine_stop'),
      danger: true,
      requireReason: true,
      onConfirm: ({ reason }) => api.engineStop(reason),
    });
    if (result.confirmed) {
      toasts.success(t('action.succeeded'));
      sync.refresh('overview');
    }
  }

  async acknowledge(code) {
    try {
      await api.acknowledgeFault(code);
      toasts.info('Инцидент отмечен в журнале');
    } catch (error) {
      toasts.error(error.message, error.correlationId);
    }
  }

  async closePosition(row) {
    // The full trading-tier gate: typed ticker confirmation, a stored reason, and
    // an idempotency key minted once per intent so a double click cannot double-fire.
    const idempotencyKey = newIdempotencyKey('position.close');
    const result = await confirmDialog({
      title: `${t('positions.close')} ${row.ticker}`,
      body: el('div', {}, [
        el('p', { text: `${fmt.quantity(row.quantity, t('unit.pieces'))} ${row.ticker}, вход ${fmt.price(row.entry_price)}.` }),
        el('p', {
          text: fmt.isNumber(row.unrealized_pnl)
            ? `Текущий нереализованный результат: ${fmt.money(row.unrealized_pnl, { signed: true })}.`
            : 'Нет котировки — текущий результат неизвестен.',
        }),
        row.mark_is_stale
          ? el('p', { className: 'qf-state-detail',
            text: `Котировка устарела на ${fmt.age(row.mark_age_seconds)} — цена закрытия может отличаться.` })
          : null,
      ]),
      confirmLabel: t('positions.close'),
      danger: true,
      typedConfirmation: row.ticker,
      requireReason: true,
      onConfirm: ({ reason }) => api.closePosition(row.id, {
        reason, confirm: row.ticker, idempotencyKey,
      }),
    });
    if (result.confirmed) {
      const pnl = result.outcome && result.outcome.data && result.outcome.data.pnl;
      toasts.success(`${row.ticker}: ${t('action.succeeded')}`,
        fmt.isNumber(pnl) ? fmt.money(pnl, { signed: true }) : undefined);
      sync.refresh('positions');
      sync.refresh('overview');
    }
  }

  async clearCredential(key, label) {
    const result = await confirmDialog({
      title: `${t('settings.clear')}: ${label}`,
      body: 'Значение будет удалено. Связанные функции перестанут работать до повторной настройки.',
      confirmLabel: t('settings.clear'),
      danger: true,
      typedConfirmation: key,
      requireReason: true,
      onConfirm: ({ reason }) => api.clearCredential(key, reason),
    });
    if (result.confirmed) {
      toasts.success(t('action.succeeded'));
      sync.refresh('credentials');
    }
  }

  async changePassword() {
    const current = el('input', { className: 'qf-input', attrs: { type: 'password', id: 'pw-current', autocomplete: 'current-password' } });
    const next = el('input', { className: 'qf-input', attrs: { type: 'password', id: 'pw-new', autocomplete: 'new-password' } });
    const result = await confirmDialog({
      title: t('settings.change_password'),
      body: el('div', {}, [
        el('div', { className: 'qf-field' }, [
          el('label', { className: 'qf-field-label', text: 'Текущий пароль', attrs: { for: 'pw-current' } }),
          current,
        ]),
        el('div', { className: 'qf-field' }, [
          el('label', { className: 'qf-field-label', text: 'Новый пароль (мин. 12 символов)', attrs: { for: 'pw-new' } }),
          next,
        ]),
        el('p', { className: 'qf-state-detail', text: 'Все остальные сессии будут завершены.' }),
      ]),
      confirmLabel: t('settings.save'),
      onConfirm: () => api.changePassword(current.value, next.value),
    });
    if (result.confirmed) {
      toasts.success('Пароль изменён. Войдите заново.');
      window.setTimeout(() => window.location.assign('/login'), 1500);
    }
  }

  async logout() {
    try {
      await api.logout();
    } catch {
      // Even a failed logout should leave the client — the cookie may already
      // be invalid, and staying on an authenticated screen is worse.
    }
    this.dispose();
    window.location.assign('/login');
  }

  handleSessionLoss() {
    toasts.error('Сессия истекла. Выполните вход заново.');
    this.dispose();
    window.setTimeout(() => window.location.assign('/login'), 1200);
  }

  // ── Shell controls and shortcuts ───────────────────────────────────────────

  bindShellControls() {
    const refresh = maybeById('qf-refresh');
    if (refresh) refresh.addEventListener('click', () => sync.refresh());

    const toggle = maybeById('qf-sidebar-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const state = this.appRoot.dataset.sidebar === 'expanded' ? 'rail' : 'expanded';
        this.appRoot.dataset.sidebar = state;
        toggle.setAttribute('aria-expanded', state === 'expanded' ? 'true' : 'false');
        try {
          window.localStorage.setItem('qf.sidebar', state);
        } catch { /* ignore */ }
      });
      const saved = window.localStorage.getItem('qf.sidebar');
      if (saved) this.appRoot.dataset.sidebar = saved;
    }

    const menu = maybeById('qf-menu');
    if (menu) {
      menu.addEventListener('click', () => {
        this.appRoot.dataset.sidebar = this.appRoot.dataset.sidebar === 'open' ? 'rail' : 'open';
      });
    }

    const logout = maybeById('qf-logout');
    if (logout) logout.addEventListener('click', () => this.logout());
  }

  bindShortcuts() {
    // Single letters only, no modifiers, disabled in inputs — so ⌘R and ⌘1–⌘9
    // reach the browser.
    this.shortcuts.bind('r', () => sync.refresh(), t('shell.refresh'));
    this.shortcuts.bind('o', () => this.router.navigate('overview'), t('nav.overview'));
    this.shortcuts.bind('p', () => this.router.navigate('positions'), t('nav.positions'));
    this.shortcuts.bind('t', () => this.router.navigate('trades'), t('nav.trades'));
    this.shortcuts.bind('s', () => this.router.navigate('signals'), t('nav.signals'));
    this.shortcuts.bind('h', () => this.router.navigate('health'), t('nav.health'));
    this.shortcuts.bind('j', () => this.router.navigate('events'), t('nav.events'));
    this.shortcuts.bind('?', () => this.showShortcuts(), t('shell.shortcuts'));
  }

  showShortcuts() {
    confirmDialog({
      title: t('shell.shortcuts'),
      body: el('ul', {}, this.shortcuts.list().map((item) =>
        el('li', { className: 'qf-caption', text: `${item.key} — ${item.description}` }))),
      confirmLabel: 'Закрыть',
      onConfirm: () => Promise.resolve(),
    });
  }

  // ── View context ───────────────────────────────────────────────────────────

  context() {
    return {
      api,
      charts: this.charts,
      session: this.session,
      subscribe: (name, listener) => store.subscribe(name, listener),
      refresh: (name) => sync.refresh(name),
      params: () => this.router.params(),
      setParams: (params) => this.router.setParams({ ...this.router.params(), ...params }),
      onParamsChange: (listener) => {
        this.paramListeners.add(listener);
        return () => this.paramListeners.delete(listener);
      },
      closePosition: (row) => this.closePosition(row),
      clearCredential: (key, label) => this.clearCredential(key, label),
      changePassword: () => this.changePassword(),
      logout: () => this.logout(),
      density: () => this.density,
      setDensity: (value) => {
        this.density = value;
        document.documentElement.dataset.density = value;
        try {
          window.localStorage.setItem('qf.density', value);
        } catch { /* ignore */ }
      },
      shortcuts: () => this.shortcuts.list(),
      shortcutsEnabled: () => this.shortcuts.enabled,
      setShortcutsEnabled: (value) => this.shortcuts.setEnabled(value),
      navigate: (id) => this.router.navigate(id),
    };
  }
}

const app = new App();
app.start().catch((error) => {
  // A boot failure must be visible. The old client's four HTTP 500s produced a
  // clean console and four panels stuck on «Loading…» forever.
  const root = document.getElementById('qf-content');
  if (root) {
    render(root, el('div', { className: 'qf-state qf-state--error', attrs: { role: 'alert' } }, [
      el('div', { className: 'qf-state-title', text: 'Не удалось запустить дашборд' }),
      el('div', { className: 'qf-state-detail', text: error && error.message ? error.message : String(error) }),
    ]));
  }
});

// Exposed for the read-only QA pass and the Playwright checks: request rate,
// listener count and chart count are the three leak canaries.
window.__qf = {
  store, sync, app,
  diagnostics: () => ({
    requestsPerMinute: sync.projectedRequestsPerMinute(),
    listeners: store.totalListeners(),
    charts: app.charts.size,
    slices: store.names(),
    tasks: sync.diagnostics(),
  }),
};
