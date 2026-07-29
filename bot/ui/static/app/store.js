/**
 * Per-slice server state.
 *
 * Two defects this replaces.
 *
 * **The unsubscribe was a permanent no-op.** `QFStore.on()` returned a closure
 * that removed the *wrong* function reference, so every subscriber ever
 * registered stayed registered — render functions accumulated across view
 * switches and each poll invoked all of them. The test for this module is
 * literally that subscribe-then-unsubscribe leaves zero listeners.
 *
 * **One global freshness flag for the whole screen.** `fullSync` used
 * `Promise.allSettled`, silently dropped rejected slices, then unconditionally
 * set `syncStatus: 'live'` and stamped «обновлено HH:MM:SS» with a green dot. A
 * screen full of 32-day-old numbers was labelled fresh. Here every slice owns its
 * own status, and the global status is the *worst* of them — never the average and
 * never the optimistic one.
 */

/** A slice's lifecycle. Ten states, because ten things can be true. */
export const SliceState = {
  IDLE: 'idle',
  LOADING: 'loading',            // first load, nothing to show yet
  REFRESHING: 'refreshing',      // has data, fetching again — keep showing it
  LOADED: 'loaded',
  EMPTY: 'empty',
  PARTIAL: 'partial',
  STALE: 'stale',
  DISCONNECTED: 'disconnected',
  FORBIDDEN: 'forbidden',
  ERROR: 'error',
};

/** Severity for combining slices. Higher wins when computing global status. */
const SEVERITY = {
  [SliceState.LOADED]: 0,
  [SliceState.EMPTY]: 0,
  [SliceState.IDLE]: 1,
  [SliceState.LOADING]: 1,
  [SliceState.REFRESHING]: 1,
  [SliceState.PARTIAL]: 2,
  [SliceState.STALE]: 3,
  [SliceState.FORBIDDEN]: 3,
  [SliceState.DISCONNECTED]: 4,
  [SliceState.ERROR]: 4,
};

class Slice {
  constructor(name) {
    this.name = name;
    this.state = SliceState.IDLE;
    this.data = null;
    this.meta = null;
    this.error = null;
    /** When *this slice* last completed successfully. Not when the page polled. */
    this.updatedAt = null;
    this.consecutiveFailures = 0;
    this.listeners = new Set();
  }

  get hasData() {
    return this.data !== null && this.data !== undefined;
  }

  /**
   * Whether the slice's *source data* is stale, from the contract's own fields.
   *
   * `meta.is_stale` is authoritative when present because the server knows the
   * per-timeframe threshold. `null` means unknown, and unknown is not fresh.
   */
  get isStale() {
    if (!this.meta) return null;
    if (typeof this.meta.is_stale === 'boolean') return this.meta.is_stale;
    const age = this.meta.data_age_seconds;
    const threshold = this.meta.stale_after_seconds;
    if (typeof age !== 'number' || typeof threshold !== 'number') return null;
    return age > threshold;
  }

  get isPartial() {
    return Boolean(this.meta && this.meta.partial);
  }
}

class Store {
  constructor() {
    this.slices = new Map();
    this.globalListeners = new Set();
  }

  slice(name) {
    let existing = this.slices.get(name);
    if (!existing) {
      existing = new Slice(name);
      this.slices.set(name, existing);
    }
    return existing;
  }

  /**
   * Subscribe to a slice. Returns a working unsubscribe.
   *
   * The listener is called immediately with the current snapshot so a view that
   * mounts after data has arrived renders straight away instead of waiting a full
   * poll interval.
   */
  subscribe(name, listener) {
    const slice = this.slice(name);
    slice.listeners.add(listener);
    try {
      listener(this.snapshot(name));
    } catch (error) {
      reportListenerError(name, error);
    }
    // Closes over the exact Set and the exact function reference.
    return () => {
      slice.listeners.delete(listener);
    };
  }

  subscribeGlobal(listener) {
    this.globalListeners.add(listener);
    try {
      listener(this.globalStatus());
    } catch (error) {
      reportListenerError('global', error);
    }
    return () => {
      this.globalListeners.delete(listener);
    };
  }

  listenerCount(name) {
    return name ? this.slice(name).listeners.size : this.globalListeners.size;
  }

  snapshot(name) {
    const slice = this.slice(name);
    return {
      name,
      state: slice.state,
      data: slice.data,
      meta: slice.meta,
      error: slice.error,
      updatedAt: slice.updatedAt,
      hasData: slice.hasData,
      isStale: slice.isStale,
      isPartial: slice.isPartial,
    };
  }

  /** Mark a fetch as started. Keeps existing data visible. */
  beginLoad(name) {
    const slice = this.slice(name);
    slice.state = slice.hasData ? SliceState.REFRESHING : SliceState.LOADING;
    this.emit(name);
  }

  /**
   * Record a successful fetch.
   *
   * The resulting state is derived from the payload rather than assumed: stale
   * beats partial beats empty beats loaded, so a slice that arrived complete but
   * old is reported as stale rather than as loaded.
   */
  succeed(name, { data, meta }, { isEmpty } = {}) {
    const slice = this.slice(name);
    slice.data = data;
    slice.meta = meta || {};
    slice.error = null;
    slice.updatedAt = Date.now();
    slice.consecutiveFailures = 0;

    const empty = typeof isEmpty === 'function'
      ? isEmpty(data, slice.meta)
      : Boolean(slice.meta.empty_reason);

    if (slice.isStale === true) slice.state = SliceState.STALE;
    else if (slice.isPartial) slice.state = SliceState.PARTIAL;
    else if (empty) slice.state = SliceState.EMPTY;
    else slice.state = SliceState.LOADED;

    this.emit(name);
  }

  /**
   * Record a failure. Existing data is retained and stays visible.
   *
   * Clearing a populated panel on failure is what made an outage look like "no
   * trades today". The panel keeps its numbers, visibly marked as not current.
   */
  fail(name, error) {
    const slice = this.slice(name);
    slice.error = error;
    slice.consecutiveFailures += 1;
    if (error && error.code === 'FORBIDDEN') slice.state = SliceState.FORBIDDEN;
    else if (error && (error.status === 0 || error.code === 'DB_UNAVAILABLE')) {
      slice.state = SliceState.DISCONNECTED;
    } else slice.state = SliceState.ERROR;
    this.emit(name);
  }

  reset(name) {
    const slice = this.slice(name);
    slice.state = SliceState.IDLE;
    slice.data = null;
    slice.meta = null;
    slice.error = null;
    slice.updatedAt = null;
    slice.consecutiveFailures = 0;
    this.emit(name);
  }

  emit(name) {
    const slice = this.slice(name);
    const snapshot = this.snapshot(name);
    for (const listener of Array.from(slice.listeners)) {
      try {
        listener(snapshot);
      } catch (error) {
        reportListenerError(name, error);
      }
    }
    this.emitGlobal();
  }

  emitGlobal() {
    const status = this.globalStatus();
    for (const listener of Array.from(this.globalListeners)) {
      try {
        listener(status);
      } catch (error) {
        reportListenerError('global', error);
      }
    }
  }

  /**
   * The screen's overall status: the worst of the slices that carry data.
   *
   * Slices still idle are excluded — a view not yet visited should not make the
   * whole screen look degraded. Everything else counts, and the *reason* travels
   * with the verdict so the topbar can name what is wrong rather than just
   * colouring a dot.
   */
  globalStatus() {
    let worst = SliceState.LOADED;
    let worstSlice = null;
    let newest = null;
    let oldestSource = null;
    let tracked = 0;

    for (const slice of this.slices.values()) {
      if (slice.state === SliceState.IDLE) continue;
      tracked += 1;
      if ((SEVERITY[slice.state] ?? 0) > (SEVERITY[worst] ?? 0)) {
        worst = slice.state;
        worstSlice = slice.name;
      }
      if (slice.updatedAt && (newest === null || slice.updatedAt > newest)) {
        newest = slice.updatedAt;
      }
      const age = slice.meta && slice.meta.data_age_seconds;
      if (typeof age === 'number' && (oldestSource === null || age > oldestSource)) {
        oldestSource = age;
      }
    }

    return {
      state: tracked ? worst : SliceState.IDLE,
      worstSlice,
      lastUpdatedAt: newest,
      oldestSourceAgeSeconds: oldestSource,
      trackedSlices: tracked,
      // Explicitly *not* "live unless proven otherwise".
      isHealthy: tracked > 0 && (SEVERITY[worst] ?? 0) === 0,
    };
  }

  /** Every registered slice name, for diagnostics. */
  names() {
    return Array.from(this.slices.keys());
  }

  /** Total listeners across all slices — the leak canary. */
  totalListeners() {
    let total = this.globalListeners.size;
    for (const slice of this.slices.values()) total += slice.listeners.size;
    return total;
  }
}

function reportListenerError(name, error) {
  // A broken listener must not take the poll loop down with it, and it must not
  // be swallowed either — a console.warn-only failure is how four HTTP 500s
  // produced a clean browser console.
  window.dispatchEvent(new CustomEvent('qf:listener-error', {
    detail: { slice: name, error },
  }));
}

export const store = new Store();
export { Store };
