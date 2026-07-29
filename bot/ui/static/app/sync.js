/**
 * Polling. Visibility-aware, backed off, per-slice, and never overlapping.
 *
 * What this replaces, measured: `POLL_MS = 12000` firing a nine-request batch,
 * four of which independently recomputed the whole paper portfolio; plus the
 * Learning view's own 20-second timer firing five more; plus the mini-app's
 * 12-second timer. 45–54 requests/minute at idle, ~360/min while navigating, and
 * `grep visibilitychange` over the whole client returned nothing — a backgrounded
 * tab kept polling, kept calling the broker and kept inserting equity snapshots.
 * A batch spanned 13 seconds against a 12-second interval, so the UI was
 * permanently mid-load and the client's own 12-second abort cancelled its own
 * requests.
 *
 * The rules here:
 *
 * * One registration per slice. Two loops for one slice cannot exist.
 * * A cycle never starts while the previous one for that slice is in flight.
 * * `document.visibilityState === 'hidden'` slows everything to a heartbeat.
 * * Failures back off exponentially with jitter, and a broker failure is cached
 *   negatively so it is not retried at full rate.
 * * Target: ≤12 requests/minute per active tab.
 */

import { AbortedError, ApiError } from './api.js';
import { store } from './store.js';

/** Base intervals. The Overview is one composed request, so 10s is affordable. */
export const Cadence = {
  FAST: 10000,    // environment + overview
  NORMAL: 30000,  // positions, signals, risk
  SLOW: 60000,    // trades, strategies, statistics
  LAZY: 300000,   // events, audit, coverage
};

/** A hidden tab drops to this regardless of the slice's own cadence. */
const HIDDEN_INTERVAL = 120000;

/** Backoff ceiling. Beyond this a failing endpoint is checked twice a minute. */
const MAX_BACKOFF = 120000;

class Task {
  constructor({ name, fetcher, interval, isEmpty, enabled }) {
    this.name = name;
    this.fetcher = fetcher;
    this.interval = interval;
    this.isEmpty = isEmpty;
    /** Predicate: a slice only polls while its view needs it. */
    this.enabled = enabled || (() => true);
    this.timer = null;
    this.inFlight = false;
    this.lastRunAt = 0;
    this.failures = 0;
    this.disposed = false;
  }

  /** Current wait, accounting for backoff and tab visibility. */
  nextDelay() {
    if (document.visibilityState === 'hidden') return HIDDEN_INTERVAL;
    if (this.failures === 0) return this.interval;
    // Exponential with full jitter: a synchronised retry storm across slices
    // would hit a five-connection pool all at once.
    const exponential = Math.min(MAX_BACKOFF, this.interval * 2 ** Math.min(this.failures, 6));
    return Math.round(exponential / 2 + Math.random() * (exponential / 2));
  }
}

class Sync {
  constructor() {
    this.tasks = new Map();
    this.started = false;
    this.onVisibility = this.handleVisibility.bind(this);
    this.onOnline = this.handleOnline.bind(this);
  }

  /**
   * Register a slice. Re-registering replaces the previous task rather than
   * adding a second loop for the same slice.
   */
  register({ name, fetcher, interval = Cadence.NORMAL, isEmpty, enabled }) {
    const existing = this.tasks.get(name);
    if (existing) this.stopTask(existing);
    const task = new Task({ name, fetcher, interval, isEmpty, enabled });
    this.tasks.set(name, task);
    if (this.started) this.schedule(task, 0);
    return () => this.unregister(name);
  }

  unregister(name) {
    const task = this.tasks.get(name);
    if (!task) return;
    this.stopTask(task);
    this.tasks.delete(name);
  }

  stopTask(task) {
    task.disposed = true;
    if (task.timer) {
      window.clearTimeout(task.timer);
      task.timer = null;
    }
  }

  start() {
    if (this.started) return;
    this.started = true;
    document.addEventListener('visibilitychange', this.onVisibility);
    window.addEventListener('online', this.onOnline);
    for (const task of this.tasks.values()) this.schedule(task, 0);
  }

  stop() {
    this.started = false;
    document.removeEventListener('visibilitychange', this.onVisibility);
    window.removeEventListener('online', this.onOnline);
    for (const task of this.tasks.values()) this.stopTask(task);
  }

  schedule(task, delay) {
    if (task.disposed || !this.started) return;
    if (task.timer) window.clearTimeout(task.timer);
    task.timer = window.setTimeout(() => this.run(task), delay);
  }

  async run(task) {
    if (task.disposed || !this.started) return;

    if (!task.enabled()) {
      // Not needed by the current view. Check back at the base interval rather
      // than spinning.
      this.schedule(task, task.interval);
      return;
    }

    // The overlap guard. A cycle that is still running does not get a second one
    // stacked behind it, which is what produced permanently-mid-load screens.
    if (task.inFlight) {
      this.schedule(task, 1000);
      return;
    }

    task.inFlight = true;
    task.lastRunAt = Date.now();
    store.beginLoad(task.name);

    try {
      const result = await task.fetcher();
      if (task.disposed) return;
      store.succeed(task.name, result, { isEmpty: task.isEmpty });
      task.failures = 0;
    } catch (error) {
      if (task.disposed) return;
      if (error instanceof AbortedError) {
        // The caller cancelled — a view switch, not a failure. Do not back off.
        task.inFlight = false;
        this.schedule(task, task.interval);
        return;
      }
      store.fail(task.name, error);
      task.failures += 1;

      if (error instanceof ApiError && error.needsAuth) {
        // No amount of retrying fixes an expired session.
        this.stop();
        window.dispatchEvent(new CustomEvent('qf:unauthenticated'));
        return;
      }
    } finally {
      task.inFlight = false;
    }

    this.schedule(task, task.nextDelay());
  }

  /**
   * Refresh now, on operator demand.
   *
   * Resets backoff: an operator pressing refresh is asserting that whatever was
   * wrong may be fixed, and making them wait out an exponential delay is hostile.
   */
  refresh(name) {
    const names = name ? [name] : Array.from(this.tasks.keys());
    for (const key of names) {
      const task = this.tasks.get(key);
      if (!task) continue;
      task.failures = 0;
      this.schedule(task, 0);
    }
  }

  handleVisibility() {
    if (document.visibilityState !== 'visible') {
      // Reschedule at the hidden cadence immediately rather than letting the
      // current fast timer fire once more.
      for (const task of this.tasks.values()) this.schedule(task, HIDDEN_INTERVAL);
      return;
    }
    // Coming back: refresh anything whose data is older than its own interval,
    // and leave the rest alone so returning to a tab is not a request storm.
    const now = Date.now();
    for (const task of this.tasks.values()) {
      const elapsed = now - task.lastRunAt;
      this.schedule(task, elapsed >= task.interval ? 0 : task.interval - elapsed);
    }
  }

  handleOnline() {
    // Connectivity returned; clear backoff so recovery is immediate.
    this.refresh();
  }

  /** Requests per minute at the current cadence — asserted by a test. */
  projectedRequestsPerMinute() {
    let total = 0;
    for (const task of this.tasks.values()) {
      if (!task.enabled()) continue;
      total += 60000 / task.nextDelay();
    }
    return Math.round(total * 10) / 10;
  }

  diagnostics() {
    return Array.from(this.tasks.values()).map((task) => ({
      name: task.name,
      interval: task.interval,
      nextDelay: task.nextDelay(),
      failures: task.failures,
      inFlight: task.inFlight,
      enabled: task.enabled(),
    }));
  }
}

export const sync = new Sync();

/**
 * Server-sent events, as a *hint* rather than a data channel.
 *
 * The SSE endpoint blocks a worker per client inside `stream_with_context`, so the
 * dev server's threading is load-bearing and behind gunicorn's default sync worker
 * N workers would mean N total viewers. Treating an event as "refresh this slice
 * now" rather than as the payload itself keeps the dashboard fully functional when
 * SSE is unavailable, which it will be in any real deployment.
 */
export class EventStream {
  constructor(url = '/api/platform/stream') {
    this.url = url;
    this.source = null;
    this.handlers = new Map();
    this.retryDelay = 5000;
    this.retryTimer = null;
    this.disposed = false;
  }

  on(eventType, handler) {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set());
    this.handlers.get(eventType).add(handler);
    return () => {
      const set = this.handlers.get(eventType);
      if (set) set.delete(handler);
    };
  }

  connect() {
    if (this.disposed || this.source) return;
    try {
      this.source = new EventSource(this.url, { withCredentials: true });
    } catch {
      return;
    }

    this.source.addEventListener('message', (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      const type = payload && payload.type;
      const handlers = this.handlers.get(type);
      if (handlers) for (const handler of handlers) handler(payload.data);
      const any = this.handlers.get('*');
      if (any) for (const handler of any) handler(payload);
    });

    this.source.addEventListener('error', () => {
      // EventSource retries on its own, but it does not close, so a dead
      // connection lingers. Close and schedule an explicit reconnect.
      this.close();
      if (!this.disposed) {
        this.retryTimer = window.setTimeout(() => this.connect(), this.retryDelay);
        this.retryDelay = Math.min(60000, this.retryDelay * 2);
      }
    });

    this.source.addEventListener('open', () => {
      this.retryDelay = 5000;
    });
  }

  close() {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
    if (this.retryTimer) {
      window.clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }

  /** Called on logout and on page unload — an unclosed EventSource is a leak. */
  dispose() {
    this.disposed = true;
    this.handlers.clear();
    this.close();
  }
}
