/**
 * The single formatting authority.
 *
 * Every number, sign, currency, percentage, timestamp and age in the interface is
 * produced here. The old code formatted the same quantity differently in different
 * places, which is how «н/д», «—», «0,00 %» and «+0,00 ₽» all came to mean
 * "there is no data" on one screen — and how a measured zero became
 * indistinguishable from an absent measurement.
 *
 * Three rules the whole module exists to enforce:
 *
 * 1. `null` / `undefined` is **not** zero. An absent measurement renders as `н/д`,
 *    never as `0,00`. `+0,00 ₽` asserting a measured result of zero where none was
 *    measured is the most dangerous rendering in a trading interface.
 * 2. Russian locale, with the correct characters: U+00A0 as the thousands
 *    separator and before a unit, U+2212 (real minus) rather than a hyphen.
 * 3. Money and its currency are one atom. The balance tile wrapped `₽` onto a
 *    second line at 1600px because the symbol was part of the wrapping run.
 */

/** Non-breaking space. Between digits and between a value and its unit. */
export const NBSP = ' ';
/** Real minus sign. A hyphen is a different, narrower glyph and misaligns columns. */
export const MINUS = '−';
/** Middle dot, for «0,61 · выборка 12». */
export const MIDDOT = '·';
/** What an absent measurement looks like. Never a zero, never an em dash alone. */
export const NO_DATA = 'н/д';

const LOCALE = 'ru-RU';

/** Intl instances are expensive to construct; build each shape once. */
const cache = new Map();

function formatter(digits) {
  const key = `d${digits}`;
  let instance = cache.get(key);
  if (!instance) {
    instance = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      useGrouping: true,
    });
    cache.set(key, instance);
  }
  return instance;
}

/**
 * Normalise Intl output: force NBSP separators and a real minus.
 *
 * `Intl.NumberFormat('ru-RU')` emits U+00A0 in modern engines but has historically
 * emitted a plain space, and it always emits U+2212 for negatives in `ru-RU` —
 * neither is safe to assume across the browsers an operator might use.
 */
function normalise(text) {
  return text.replace(/ |\s/g, NBSP).replace(/^-/, MINUS);
}

/** True only for a real, finite number. Strings and NaN are not measurements. */
export function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Signed prefix. `+` is explicit because in greyscale the sign is what carries
 * profit-versus-loss — colour is reinforcement only.
 */
function signPrefix(value, signed) {
  if (!signed) return '';
  if (value > 0) return '+';
  return '';
}

/** Currency symbol per ISO code. Falls back to the code itself. */
const CURRENCY_SYMBOL = { RUB: '₽', USD: '$', EUR: '€', USDT: 'USDT' };

export function currencySymbol(code) {
  return CURRENCY_SYMBOL[code] || code || '';
}

/**
 * Money. `1 038 050,00 ₽`, `+12 480,50 ₽`, `−3 200,00 ₽`.
 *
 * Never abbreviated to `1,04M` on a trading surface: an operator reconciling a
 * balance needs the digits.
 */
export function money(value, { currency = 'RUB', signed = false, digits = 2 } = {}) {
  if (!isNumber(value)) return NO_DATA;
  // -0 must render as 0, not as «−0,00 ₽».
  const safe = Object.is(value, -0) ? 0 : value;
  const body = normalise(formatter(digits).format(safe));
  const symbol = currencySymbol(currency);
  return `${signPrefix(safe, signed)}${body}${symbol ? NBSP + symbol : ''}`;
}

/** Percentage. `+1,24 %`, `−8,08 %`. NBSP before the sign, per Russian typography. */
export function percent(value, { signed = true, digits = 2 } = {}) {
  if (!isNumber(value)) return NO_DATA;
  const safe = Object.is(value, -0) ? 0 : value;
  return `${signPrefix(safe, signed)}${normalise(formatter(digits).format(safe))}${NBSP}%`;
}

/** A bare number at fixed precision. */
export function number(value, digits = 2) {
  if (!isNumber(value)) return NO_DATA;
  return normalise(formatter(digits).format(Object.is(value, -0) ? 0 : value));
}

export function integer(value) {
  if (!isNumber(value)) return NO_DATA;
  return normalise(formatter(0).format(value));
}

/**
 * A price at the instrument's own precision.
 *
 * A global 2 dp is wrong in both directions: `29,9500` for a 4-dp instrument is
 * noise, and 2 dp on a 4-dp instrument silently rounds away a tick. Precision is
 * inferred from the value's own magnitude, which is the best available signal
 * until the API carries a tick size.
 */
export function price(value, { digits } = {}) {
  if (!isNumber(value)) return NO_DATA;
  const resolved = digits ?? (Math.abs(value) >= 100 ? 2 : Math.abs(value) >= 1 ? 3 : 5);
  return normalise(formatter(resolved).format(value));
}

/** R multiples. `+1,8R` / `−1,0R`. `R` is a unit, never a colour. */
export function rMultiple(value) {
  if (!isNumber(value)) return NO_DATA;
  return `${signPrefix(value, true)}${normalise(formatter(1).format(value))}R`;
}

/**
 * Profit factor. `1,64`, or `∞` only when the sample justifies the claim.
 *
 * Never `0` for "undefined": zero profit factor is a real, terrible result and
 * must not share a rendering with "no losses yet".
 */
export function profitFactor(value, { n = 0, undefinedReason = null } = {}) {
  if (isNumber(value)) return number(value, 2);
  if (undefinedReason === 'нет убыточных сделок' && n >= 30) return '∞';
  return NO_DATA;
}

/**
 * Win rate with its numerator and denominator — the count is mandatory.
 *
 * `54,2 % (26 из 48)`. Without the count, `0,00 %` from zero trades and a genuine
 * 0 % over 48 trades render identically.
 */
export function winRate(pct, wins, n) {
  if (!isNumber(pct) || !n) return `${NO_DATA} (0 сделок)`;
  return `${normalise(formatter(1).format(pct))}${NBSP}% (${integer(wins)} из ${integer(n)})`;
}

/**
 * Confidence — only ever with its sample size. `0,61 · выборка 12`.
 *
 * Never as a percentage: it is a strategy-level statistical score, not the
 * probability of a profitable trade, and a `%` sign invites exactly that misread.
 */
export function confidence(value, sampleSize) {
  if (!isNumber(value)) return NO_DATA;
  const size = isNumber(sampleSize) ? sampleSize : 0;
  return `${number(value, 2)}${NBSP}${MIDDOT}${NBSP}выборка${NBSP}${integer(size)}`;
}

/** Sample-size suffix for any other statistic. */
export function sampleSuffix(n) {
  return isNumber(n) ? `n${NBSP}=${NBSP}${integer(n)}` : `n${NBSP}=${NBSP}0`;
}

/** Quantity. Lots versus units are labelled per instrument by the caller. */
export function quantity(value, unit = 'шт') {
  if (!isNumber(value)) return NO_DATA;
  const digits = Number.isInteger(value) ? 0 : 4;
  return `${normalise(formatter(digits).format(value))}${NBSP}${unit}`;
}

/** Latency. Integer milliseconds — sub-millisecond precision is noise. */
export function latency(ms) {
  if (!isNumber(ms)) return NO_DATA;
  return `${integer(Math.round(ms))}${NBSP}мс`;
}

// ── Time ─────────────────────────────────────────────────────────────────────
// The server sends ISO-8601 with an offset and names the zone in `meta.timezone`.
// The client never converts — it renders what it was given plus that label. One
// policy, applied at one boundary; converting in two places is how an equity
// x-axis silently shifts by three hours.

function parse(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** `14:07:22` — same-day only. */
export function clockTime(value) {
  const date = parse(value);
  if (!date) return NO_DATA;
  return date.toLocaleTimeString(LOCALE, {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

/** `28.07 14:07` — day-month for the current year. */
export function shortDateTime(value) {
  const date = parse(value);
  if (!date) return NO_DATA;
  return date.toLocaleString(LOCALE, {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).replace(',', '');
}

/**
 * `2026-07-28 14:07:22 MSK`. The timezone label is never optional.
 *
 * Shown on hover and in detail views, always alongside the relative age.
 */
export function absoluteTime(value, timezone = 'MSK') {
  const date = parse(value);
  if (!date) return NO_DATA;
  const iso = date.toLocaleString(LOCALE, {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).replace(',', '');
  return `${iso}${NBSP}${timezone}`;
}

/** Same-day values get a clock, older ones a date. */
export function smartTime(value) {
  const date = parse(value);
  if (!date) return NO_DATA;
  const now = new Date();
  const sameDay = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
  return sameDay ? clockTime(value) : shortDateTime(value);
}

/**
 * The staleness primitive: `42 с`, `14 мин`, `1 ч 12 мин`, `32 дн`.
 *
 * Relative and counting up. Always paired with the absolute time in a `title`, so
 * the reading is both immediate and precise.
 */
export function age(seconds) {
  if (!isNumber(seconds) || seconds < 0) return NO_DATA;
  const total = Math.floor(seconds);
  if (total < 60) return `${total}${NBSP}с`;
  if (total < 3600) return `${Math.floor(total / 60)}${NBSP}мин`;
  if (total < 86400) {
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    return minutes ? `${hours}${NBSP}ч ${minutes}${NBSP}мин` : `${hours}${NBSP}ч`;
  }
  return `${Math.floor(total / 86400)}${NBSP}дн`;
}

/** `42 с назад`, for a sentence rather than a badge. */
export function ageAgo(seconds) {
  const text = age(seconds);
  return text === NO_DATA ? NO_DATA : `${text} назад`;
}

/** Trade duration. Coarser than `age` — nobody holds a position for 42 seconds. */
export function duration(seconds) {
  if (!isNumber(seconds) || seconds < 0) return NO_DATA;
  const total = Math.floor(seconds);
  if (total < 3600) return `${Math.floor(total / 60)}${NBSP}мин`;
  if (total < 86400) return `${(total / 3600).toFixed(1).replace('.', ',')}${NBSP}ч`;
  return `${(total / 86400).toFixed(1).replace('.', ',')}${NBSP}дн`;
}

// ── Sign classification ──────────────────────────────────────────────────────

/**
 * The CSS class for a value's sign.
 *
 * `unknown` is distinct from `neutral`: a measured zero is neutral, an absent
 * measurement is unknown, and they must not look the same.
 */
export function signClass(value) {
  if (!isNumber(value)) return 'qf-unknown-value';
  if (value > 0) return 'qf-positive';
  if (value < 0) return 'qf-negative';
  return 'qf-neutral-value';
}

/** Whether a value should be treated as stale given its age and threshold. */
export function isStale(ageSeconds, threshold) {
  if (!isNumber(ageSeconds) || !isNumber(threshold)) return null;
  return ageSeconds > threshold;
}
