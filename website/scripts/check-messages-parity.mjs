#!/usr/bin/env node
/**
 * Fails the build if messages/en.json and messages/ru.json drift apart.
 *
 * There was previously no guard on the UI strings at all — only on `content/`.
 * That gap mattered: RU/EN parity is a hard product requirement, this redesign
 * moves the leaf count from 184 to ~258 per locale, and a missing key does not
 * fail the build. It throws `MISSING_MESSAGE` at runtime, in the browser, in
 * whichever locale nobody happened to open.
 *
 * Also catches two subtler failures a key-set diff alone would miss:
 *   - a key present in both but left as an untranslated copy of the English
 *   - a key whose ICU placeholders ({name}, {count}) differ between locales,
 *     which throws at format time rather than render time
 *
 * Run via `npm run check:i18n`.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";

const MESSAGES_DIR = path.join(process.cwd(), "messages");
const LOCALES = ["en", "ru"];

/**
 * Values legitimately identical across locales: proper nouns, product names,
 * technical identifiers, symbols. Anything else matching byte-for-byte is
 * almost certainly an untranslated placeholder.
 */
const IDENTICAL_OK = new Set([
  "Quant",
  "Telegram",
  "MOEX",
  "Bybit",
  "T-Invest",
  "Finam",
  "Dashboard",
  "API",
  "Explore",
  "Sandbox",
  "Live",
  "Premium",
  "FAQ",
  "EN",
  "RU",
  "MOEX + Bybit",
  "Quant · Dashboard",
  "you@example.com",
]);

/** Purely numeric or symbolic values — "5%", "0.20", "—". Never translated. */
const NON_LINGUISTIC = /^[\d\s.,%×+—·:/-]+$/;

let hasError = false;
const warnings = [];

function fail(message) {
  console.error(`✗ ${message}`);
  hasError = true;
}

/** Flattens nested objects to dotted leaf paths. */
function flatten(obj, prefix = "", out = new Map()) {
  for (const [key, value] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      flatten(value, full, out);
    } else {
      out.set(full, value);
    }
  }
  return out;
}

/** Extracts ICU placeholder names, e.g. "{count} of {total}" -> ["count","total"]. */
function placeholders(value) {
  if (typeof value !== "string") return [];
  return [...value.matchAll(/\{(\w+)/g)].map((m) => m[1]).sort();
}

async function main() {
  const [en, ru] = await Promise.all(
    LOCALES.map(async (locale) => {
      const raw = await readFile(path.join(MESSAGES_DIR, `${locale}.json`), "utf8");
      return flatten(JSON.parse(raw));
    }),
  );

  for (const key of en.keys()) {
    if (!ru.has(key)) fail(`messages/ru.json is missing "${key}" (present in en)`);
  }
  for (const key of ru.keys()) {
    if (!en.has(key)) fail(`messages/en.json is missing "${key}" (present in ru)`);
  }

  for (const [key, enValue] of en) {
    if (!ru.has(key)) continue;
    const ruValue = ru.get(key);

    if (typeof enValue !== typeof ruValue) {
      fail(`"${key}" type differs (en=${typeof enValue} ru=${typeof ruValue})`);
      continue;
    }

    const enPh = placeholders(enValue).join(",");
    const ruPh = placeholders(ruValue).join(",");
    if (enPh !== ruPh) {
      fail(`"${key}" ICU placeholders differ (en=[${enPh}] ru=[${ruPh}])`);
    }

    if (
      typeof enValue === "string" &&
      enValue === ruValue &&
      enValue.trim() !== "" &&
      !IDENTICAL_OK.has(enValue.trim()) &&
      !NON_LINGUISTIC.test(enValue.trim())
    ) {
      warnings.push(`"${key}" is byte-identical in both locales — untranslated? (${enValue})`);
    }
  }

  for (const w of warnings) console.warn(`⚠ ${w}`);

  if (hasError) {
    console.error("\nMessage parity check failed.");
    process.exit(1);
  }
  console.log(
    `✓ messages/en.json and messages/ru.json are in parity (${en.size} keys each` +
      `${warnings.length ? `, ${warnings.length} warning(s)` : ""}).`,
  );
}

main();
