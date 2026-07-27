#!/usr/bin/env node
/**
 * Reports which hero media are present.
 *
 * ── No longer part of `npm run build` ──
 *
 * The homepage hero is a composed static object now
 * (components/sections/hero/hero-visual.tsx), so the build has no hero-media
 * dependency at all and this script was removed from the `build` script. It is
 * retained as the inventory tool for the archived video experiment — see
 * docs/VIDEO_ASSET_GUIDE.md — and is still runnable via `npm run check:media`.
 *
 * WARN-ONLY: it never fails, and "no video present" is a normal state, not an
 * error. The posters are committed; the .mp4 files are gitignored, so on CI, on
 * Vercel and in a fresh clone the optional list is simply empty.
 */
import { stat } from "node:fs/promises";
import path from "node:path";

const DIR = path.join(process.cwd(), "public/media/quant-hero");

const REQUIRED = [
  "hero-poster.avif",
  "hero-poster.webp",
  "hero-poster-mobile.avif",
  "hero-poster-mobile.webp",
];

const OPTIONAL = [
  "hero-prototype.mp4",
  "hero-desktop.mp4",
  "hero-desktop.webm",
  "hero-mobile.mp4",
];

async function sizeOf(file) {
  try {
    return (await stat(path.join(DIR, file))).size;
  } catch {
    return null;
  }
}

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

async function main() {
  let missingPoster = false;

  for (const file of REQUIRED) {
    const size = await sizeOf(file);
    if (size === null) {
      console.error(`✗ MISSING required poster: public/media/quant-hero/${file}`);
      missingPoster = true;
    } else {
      console.log(`✓ ${file.padEnd(26)} ${kb(size)}`);
    }
  }

  if (missingPoster) {
    console.error("  → regenerate with: npm run media:poster");
  }

  const present = [];
  for (const file of OPTIONAL) {
    const size = await sizeOf(file);
    if (size !== null) present.push(`${file} (${kb(size)})`);
  }

  console.log(
    present.length
      ? `  video present: ${present.join(", ")}`
      : "⚠ no hero video present — rendering poster-only.\n" +
          "  This is expected on CI/Vercel and in fresh clones; *.mp4 is gitignored.\n" +
          "  See docs/VIDEO_ASSET_GUIDE.md to add a local prototype or a production master.",
  );

  // Never fail the build — see the header comment.
  process.exit(0);
}

main();
