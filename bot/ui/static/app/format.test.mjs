/**
 * Frontend unit tests: the formatting authority, the store and the safe DOM.
 *
 * Run with the platform's own runner, no dependency to install:
 *   node --test bot/ui/static/app/
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import * as fmt from './format.js';
import { SliceState, Store } from './store.js';

// ── The rule that matters most: null is not zero ─────────────────────────────

test('an absent measurement is н/д, never a zero', () => {
  // `+0,00 ₽` asserting a measured result of zero where none was measured is the
  // most dangerous rendering in a trading interface.
  assert.equal(fmt.money(null), 'н/д');
  assert.equal(fmt.money(undefined), 'н/д');
  assert.equal(fmt.money(NaN), 'н/д');
  assert.equal(fmt.percent(null), 'н/д');
  assert.equal(fmt.number(null), 'н/д');
  assert.equal(fmt.integer(null), 'н/д');
  assert.equal(fmt.age(null), 'н/д');
  assert.equal(fmt.rMultiple(null), 'н/д');
  assert.equal(fmt.duration(null), 'н/д');
});

test('a measured zero renders as zero and is distinguishable from absent', () => {
  assert.notEqual(fmt.money(0), fmt.money(null));
  assert.ok(fmt.money(0).startsWith('0,00'));
});

test('a string is not a measurement', () => {
  assert.equal(fmt.money('123'), 'н/д');
  assert.equal(fmt.isNumber('123'), false);
});

// ── Russian typography ───────────────────────────────────────────────────────

test('money uses a non-breaking thousands separator and a real minus', () => {
  const value = fmt.money(-2373454.32);
  assert.ok(value.includes(fmt.MINUS), 'must use U+2212, not a hyphen');
  assert.ok(!value.includes('-'), 'must not contain an ASCII hyphen');
  assert.ok(value.includes(fmt.NBSP), 'separators must be U+00A0');
  assert.ok(value.includes(','), 'decimal separator must be a comma');
  assert.ok(value.endsWith(`${fmt.NBSP}₽`), 'currency joins with a non-breaking space');
});

test('money and its currency cannot be split across lines', () => {
  // The balance tile rendered `1 038 050,` on one line and `₽` on the next.
  const value = fmt.money(1038050);
  const separatorIndex = value.lastIndexOf(fmt.NBSP);
  assert.equal(value.slice(separatorIndex + 1), '₽');
  assert.ok(!/ ₽/.test(value), 'no breaking space before the symbol');
});

test('percent puts a non-breaking space before the sign', () => {
  assert.equal(fmt.percent(1.24), `+1,24${fmt.NBSP}%`);
  assert.equal(fmt.percent(-8.08), `${fmt.MINUS}8,08${fmt.NBSP}%`);
  assert.equal(fmt.percent(0), `0,00${fmt.NBSP}%`);
});

test('a signed value always carries an explicit plus', () => {
  assert.ok(fmt.money(12480.5, { signed: true }).startsWith('+'));
  assert.ok(fmt.percent(1.24).startsWith('+'));
  assert.ok(fmt.rMultiple(1.8).startsWith('+'));
});

test('negative zero renders as zero, not as minus zero', () => {
  assert.ok(!fmt.money(-0).includes(fmt.MINUS));
  assert.ok(!fmt.percent(-0).includes(fmt.MINUS));
});

// ── Statistics never render without their sample size ────────────────────────

test('confidence always carries its sample size', () => {
  const value = fmt.confidence(0.61, 12);
  assert.ok(value.includes('0,61'));
  assert.ok(value.includes('выборка'));
  assert.ok(value.includes('12'));
  // Never a percentage: it is not a probability.
  assert.ok(!value.includes('%'));
});

test('confidence with an unknown sample size still says выборка 0', () => {
  assert.ok(fmt.confidence(0.61, null).includes('выборка'));
});

test('win rate carries its numerator and denominator', () => {
  assert.equal(fmt.winRate(54.2, 26, 48), `54,2${fmt.NBSP}% (26 из 48)`);
});

test('win rate from an empty sample is not a measured zero', () => {
  assert.equal(fmt.winRate(null, 0, 0), 'н/д (0 сделок)');
  assert.notEqual(fmt.winRate(null, 0, 0), fmt.winRate(0, 0, 14));
  assert.ok(fmt.winRate(0, 0, 14).includes('0 из 14'));
});

test('profit factor is н/д when undefined and ∞ only with a mature sample', () => {
  assert.equal(fmt.profitFactor(1.64), '1,64');
  assert.equal(fmt.profitFactor(null, { n: 3, undefinedReason: 'нет убыточных сделок' }), 'н/д');
  assert.equal(fmt.profitFactor(null, { n: 40, undefinedReason: 'нет убыточных сделок' }), '∞');
  assert.equal(fmt.profitFactor(null, { n: 0, undefinedReason: 'нет сделок' }), 'н/д');
  // Never 0 for "undefined": a zero profit factor is a real, terrible result.
  assert.notEqual(fmt.profitFactor(null, {}), '0,00');
});

// ── Staleness ────────────────────────────────────────────────────────────────

test('age scales through seconds, minutes, hours and days', () => {
  assert.equal(fmt.age(42), `42${fmt.NBSP}с`);
  assert.equal(fmt.age(14 * 60), `14${fmt.NBSP}мин`);
  assert.equal(fmt.age(3600 + 12 * 60), `1${fmt.NBSP}ч 12${fmt.NBSP}мин`);
  assert.equal(fmt.age(32 * 86400), `32${fmt.NBSP}дн`);
});

test('isStale is null when either input is unknown', () => {
  // Unknown freshness must never render as fresh.
  assert.equal(fmt.isStale(null, 60), null);
  assert.equal(fmt.isStale(10, null), null);
  assert.equal(fmt.isStale(10, 60), false);
  assert.equal(fmt.isStale(120, 60), true);
});

// ── Sign classification ──────────────────────────────────────────────────────

test('sign class distinguishes a measured zero from an absent value', () => {
  assert.equal(fmt.signClass(1), 'qf-positive');
  assert.equal(fmt.signClass(-1), 'qf-negative');
  assert.equal(fmt.signClass(0), 'qf-neutral-value');
  assert.equal(fmt.signClass(null), 'qf-unknown-value');
  assert.notEqual(fmt.signClass(0), fmt.signClass(null));
});

// ── Prices at instrument precision ───────────────────────────────────────────

test('price precision follows magnitude rather than a global 2 dp', () => {
  assert.ok(fmt.price(299.5).includes(','));
  // A sub-unit instrument keeps its ticks instead of rounding them away.
  assert.ok(fmt.price(0.00012345).split(',')[1].length > 2);
});

// ── The store ────────────────────────────────────────────────────────────────

test('unsubscribe actually removes the listener', () => {
  // `QFStore.on()` returned a closure that removed the *wrong* function
  // reference, so every subscriber ever registered stayed registered.
  const store = new Store();
  let calls = 0;
  const off = store.subscribe('slice', () => { calls += 1; });
  assert.equal(store.listenerCount('slice'), 1);
  assert.equal(calls, 1, 'a subscriber receives the current snapshot immediately');

  off();
  assert.equal(store.listenerCount('slice'), 0);
  store.succeed('slice', { data: [1], meta: {} });
  assert.equal(calls, 1, 'no further calls after unsubscribing');
});

test('repeated mount and unmount does not accumulate listeners', () => {
  const store = new Store();
  for (let i = 0; i < 50; i += 1) {
    const off = store.subscribe('slice', () => {});
    off();
  }
  assert.equal(store.listenerCount('slice'), 0);
  assert.equal(store.totalListeners(), 0);
});

test('a refresh keeps existing data visible', () => {
  const store = new Store();
  store.succeed('slice', { data: [1, 2], meta: {} });
  store.beginLoad('slice');
  const snapshot = store.snapshot('slice');
  assert.equal(snapshot.state, SliceState.REFRESHING);
  assert.deepEqual(snapshot.data, [1, 2], 'data must survive a refresh');
});

test('a failure keeps existing data and marks the slice', () => {
  const store = new Store();
  store.succeed('slice', { data: [1], meta: {} });
  store.fail('slice', { code: 'DB_UNAVAILABLE', status: 503 });
  const snapshot = store.snapshot('slice');
  assert.equal(snapshot.state, SliceState.DISCONNECTED);
  assert.deepEqual(snapshot.data, [1], 'a failure must not blank a populated panel');
});

test('a stale payload is reported as stale, not as loaded', () => {
  const store = new Store();
  store.succeed('slice', {
    data: [1],
    meta: { data_age_seconds: 32 * 86400, stale_after_seconds: 60, is_stale: true },
  });
  assert.equal(store.snapshot('slice').state, SliceState.STALE);
});

test('the global status is the worst slice, never the optimistic one', () => {
  // The old client dropped failed slices from Promise.allSettled and then
  // stamped the whole screen «обновлено» with a green dot.
  const store = new Store();
  store.succeed('good', { data: [1], meta: {} });
  store.succeed('stale', {
    data: [1],
    meta: { data_age_seconds: 999999, stale_after_seconds: 60, is_stale: true },
  });
  const status = store.globalStatus();
  assert.equal(status.state, SliceState.STALE);
  assert.equal(status.isHealthy, false);
  assert.equal(status.worstSlice, 'stale');
});

test('a partial payload is reported as partial', () => {
  const store = new Store();
  store.succeed('slice', { data: {}, meta: { partial: true, missing: { positions: 'x' } } });
  assert.equal(store.snapshot('slice').state, SliceState.PARTIAL);
  assert.equal(store.globalStatus().isHealthy, false);
});

test('an empty payload is empty, not an error', () => {
  const store = new Store();
  store.succeed('slice', { data: [], meta: { empty_reason: 'NO_TRADES_EVER' } });
  assert.equal(store.snapshot('slice').state, SliceState.EMPTY);
  // An empty result is a healthy answer.
  assert.equal(store.globalStatus().isHealthy, true);
});

test('an idle slice does not drag the global status down', () => {
  const store = new Store();
  store.slice('never-visited');
  store.succeed('good', { data: [1], meta: {} });
  assert.equal(store.globalStatus().isHealthy, true);
});

test('a throwing listener does not break the store', () => {
  const store = new Store();
  // No `window` in the node runner, so the dispatch path must not be reached
  // by the happy path — the throw is caught before it.
  globalThis.window = { dispatchEvent() {} };
  globalThis.CustomEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init); } };
  store.subscribe('slice', () => { throw new Error('boom'); });
  let reached = false;
  store.subscribe('slice', () => { reached = true; });
  store.succeed('slice', { data: [1], meta: {} });
  assert.equal(reached, true, 'a broken listener must not stop the others');
});
