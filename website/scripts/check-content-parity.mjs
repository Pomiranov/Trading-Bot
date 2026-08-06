#!/usr/bin/env node
/**
 * Fails the build if content/en and content/ru drift out of sync: a
 * missing MDX file in one locale, or a strategies.json missing a strategy
 * id / status field the other locale has. Run via `npm run check:content`.
 */
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const CONTENT_ROOT = path.join(process.cwd(), "content");
const LOCALES = ["en", "ru"];
const MDX_DIRS = ["philosophy", "engine-pipeline"];
const MDX_FILES = ["learning-system.mdx"];

let hasError = false;

function fail(message) {
  console.error(`✗ ${message}`);
  hasError = true;
}

async function listMdxFiles(dir) {
  try {
    return (await readdir(dir)).filter((f) => f.endsWith(".mdx")).sort();
  } catch {
    return null;
  }
}

async function checkMdxDirParity(dir) {
  const [enFiles, ruFiles] = await Promise.all(
    LOCALES.map((locale) => listMdxFiles(path.join(CONTENT_ROOT, locale, dir))),
  );

  if (enFiles === null || ruFiles === null) {
    fail(`content/{en,ru}/${dir} — one locale is missing the directory entirely`);
    return;
  }

  const enSet = new Set(enFiles);
  const ruSet = new Set(ruFiles);
  for (const file of enSet) {
    if (!ruSet.has(file)) fail(`content/ru/${dir}/${file} is missing (present in en)`);
  }
  for (const file of ruSet) {
    if (!enSet.has(file)) fail(`content/en/${dir}/${file} is missing (present in ru)`);
  }
}

async function checkMdxFileParity(file) {
  const results = await Promise.all(
    LOCALES.map(async (locale) => {
      try {
        await readFile(path.join(CONTENT_ROOT, locale, file), "utf8");
        return true;
      } catch {
        return false;
      }
    }),
  );
  results.forEach((exists, i) => {
    if (!exists) fail(`content/${LOCALES[i]}/${file} is missing`);
  });
}

async function checkStrategiesParity() {
  const [en, ru] = await Promise.all(
    LOCALES.map(async (locale) => {
      try {
        const raw = await readFile(
          path.join(CONTENT_ROOT, locale, "strategies.json"),
          "utf8",
        );
        return JSON.parse(raw);
      } catch {
        return null;
      }
    }),
  );

  if (!en || !ru) {
    fail("content/{en,ru}/strategies.json — one locale is missing the file or it's invalid JSON");
    return;
  }

  const enIds = new Set(en.map((s) => s.id));
  const ruIds = new Set(ru.map((s) => s.id));
  for (const id of enIds) {
    if (!ruIds.has(id)) fail(`strategies.json: "${id}" present in en but missing in ru`);
  }
  for (const id of ruIds) {
    if (!enIds.has(id)) fail(`strategies.json: "${id}" present in ru but missing in en`);
  }

  // Status/market/timeframe/metrics should be factually identical across
  // locales — only prose (statusNote) should differ.
  const byId = (list) => Object.fromEntries(list.map((s) => [s.id, s]));
  const enById = byId(en);
  const ruById = byId(ru);
  for (const id of enIds) {
    if (!ruIds.has(id)) continue;
    const a = enById[id];
    const b = ruById[id];
    for (const field of ["market", "timeframe", "status", "source"]) {
      if (a[field] !== b[field]) {
        fail(`strategies.json: "${id}".${field} differs between locales (en="${a[field]}" ru="${b[field]}")`);
      }
    }
  }
}

async function main() {
  for (const dir of MDX_DIRS) await checkMdxDirParity(dir);
  for (const file of MDX_FILES) await checkMdxFileParity(file);
  await checkStrategiesParity();

  if (hasError) {
    console.error("\nContent parity check failed.");
    process.exit(1);
  }
  console.log("✓ content/en and content/ru are in parity.");
}

main();
