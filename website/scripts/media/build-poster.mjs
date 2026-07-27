#!/usr/bin/env node
/**
 * Generates the hero poster images.
 *
 * IMPORTANT — these posters are ORIGINAL, AUTHORED BRAND GRAPHICS. They are
 * NOT frames extracted from the prototype video, and they contain no part of
 * any third-party watermark or provenance mark. That is deliberate:
 *
 *   1. The prototype video carries a burned-in provenance mark. Extracting a
 *      frame would permanently commit those pixels to the repository as a
 *      production asset. Drawing the poster avoids the question entirely.
 *   2. An authored poster stays correct when the prototype is swapped for a
 *      licensed master; an extracted frame would become a wrong poster.
 *   3. It is ~2.8x smaller than an extracted frame at the same quality
 *      (6-7 KB vs ~18 KB), at an element that is a strong LCP candidate.
 *
 * This is NOT a watermark-removal measure. The video itself is always played
 * byte-for-byte unmodified, mark included. See docs/VIDEO_ASSET_GUIDE.md.
 *
 * Geometry is derived from src/components/ui/monogram.tsx so the poster, the
 * nav mark and the footer mark are one system: a 300 deg open ring with a
 * 60 deg gap at upper right, a solid node at one terminus, and a tangent tail
 * uncoiling from the other.
 *
 * Run: npm run media:poster
 */
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";

const OUT_DIR = path.join(process.cwd(), "public/media/quant-hero");

const BLACK = "#030303";
const SIGNAL = "#FF7A1A";

/**
 * The Quant aperture.
 *
 * A 320deg ring — the aperture — with a 40deg blade opening at upper right,
 * and a straight tail crossing the ring's lower-right edge. The tail is what
 * makes the form read as a Q rather than a dial or a loading spinner, and it
 * carries the concept: a decision that has cleared every gate leaves the
 * aperture along it. The orange node sits at the tail's outer terminus — the
 * single validated signal, and the only accent pixel in the mark.
 *
 * Angles are in SVG space (y down), measured from 3 o'clock.
 */
const RING_START_DEG = -20;
const RING_END_DEG = -60;
const TAIL_DEG = 45;
const TAIL_INNER = 0.52;
const TAIL_OUTER = 1.32;
const rad = (deg) => (deg * Math.PI) / 180;
const round = (n) => Math.round(n * 100) / 100;

/**
 * @param {object} o
 * @param {number} o.w        canvas width
 * @param {number} o.h        canvas height
 * @param {number} o.cx       mark centre X, as a fraction of width
 * @param {number} o.cy       mark centre Y, as a fraction of height
 * @param {number} o.r        ring radius, as a fraction of height
 * @param {number} o.stroke   ring stroke width in px
 */
function poster({ w, h, cx, cy, r, stroke }) {
  const x = w * cx;
  const y = h * cy;
  const radius = h * r;

  const pt = (deg, scale = 1) => [
    round(x + radius * scale * Math.cos(rad(deg))),
    round(y + radius * scale * Math.sin(rad(deg))),
  ];
  const [sx, sy] = pt(RING_START_DEG);
  const [ex, ey] = pt(RING_END_DEG);

  // The Q tail: a straight stroke crossing the ring's lower-right edge.
  const [tix, tiy] = pt(TAIL_DEG, TAIL_INNER);
  const [tx, ty] = pt(TAIL_DEG, TAIL_OUTER);

  const node = round(radius * 0.115);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
  <defs>
    <radialGradient id="halo" cx="${round(cx * 100)}%" cy="${round(cy * 100)}%" r="46%">
      <stop offset="0%" stop-color="${SIGNAL}" stop-opacity="0.13"/>
      <stop offset="42%" stop-color="${SIGNAL}" stop-opacity="0.035"/>
      <stop offset="100%" stop-color="${SIGNAL}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.94"/>
      <stop offset="58%" stop-color="#FFFFFF" stop-opacity="0.52"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.24"/>
    </linearGradient>
    <radialGradient id="nodeGlow">
      <stop offset="0%" stop-color="${SIGNAL}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="${SIGNAL}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="tail" gradientUnits="userSpaceOnUse"
                    x1="${tix}" y1="${tiy}" x2="${tx}" y2="${ty}">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.10"/>
      <stop offset="55%" stop-color="#FFFFFF" stop-opacity="0.62"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.88"/>
    </linearGradient>
  </defs>

  <rect width="${w}" height="${h}" fill="${BLACK}"/>
  <rect width="${w}" height="${h}" fill="url(#halo)"/>

  <g fill="none" stroke="#FFFFFF">
    <circle cx="${round(x)}" cy="${round(y)}" r="${round(radius * 1.43)}" stroke-opacity="0.045" stroke-width="1"/>
    <circle cx="${round(x)}" cy="${round(y)}" r="${round(radius * 1.21)}" stroke-opacity="0.065" stroke-width="1"/>
  </g>

  <path d="M ${sx} ${sy} A ${round(radius)} ${round(radius)} 0 1 1 ${ex} ${ey}"
        fill="none" stroke="url(#ring)" stroke-width="${stroke}" stroke-linecap="round"/>
  <path d="M ${tix} ${tiy} L ${tx} ${ty}"
        fill="none" stroke="url(#tail)" stroke-width="${stroke}" stroke-linecap="round"/>

  <circle cx="${tx}" cy="${ty}" r="${round(node * 4.2)}" fill="url(#nodeGlow)"/>
  <circle cx="${tx}" cy="${ty}" r="${node}" fill="${SIGNAL}"/>
</svg>`;
}

/**
 * Desktop mirrors the prototype's composition: subject centroid at 70% / 51%,
 * left third left empty so the hero headline has clean space beside it.
 * Mobile re-centres the mark instead of cropping the desktop frame — art
 * direction by authoring, never by cropping (cropping is what would risk
 * clipping a watermark on the video side).
 */
const VARIANTS = [
  { name: "hero-poster", svg: { w: 1280, h: 720, cx: 0.7, cy: 0.51, r: 0.208, stroke: 22 } },
  { name: "hero-poster-mobile", svg: { w: 768, h: 432, cx: 0.5, cy: 0.5, r: 0.23, stroke: 15 } },
];

/**
 * Two formats, AVIF first.
 *
 * Measured on this artwork: WebP bottoms out around 11 KB even with the halo
 * and guide rings removed entirely — large near-black areas with antialiased
 * edges are its worst case, and pushing quality down buys almost nothing while
 * introducing visible blocking. AVIF encodes the same image at roughly a third
 * of that. So AVIF carries the load and WebP is the fallback, selected by the
 * browser via <picture>. Budgets below are the measured sizes plus headroom,
 * not aspirations.
 */
const FORMATS = [
  {
    ext: "avif",
    encode: (p) => p.avif({ quality: 50, effort: 6 }),
    budget: { "hero-poster": 7 * 1024, "hero-poster-mobile": 5 * 1024 },
  },
  {
    ext: "webp",
    encode: (p) => p.webp({ quality: 72, effort: 6, smartSubsample: true }),
    budget: { "hero-poster": 16 * 1024, "hero-poster-mobile": 9 * 1024 },
  },
];

async function main() {
  let sharp;
  try {
    ({ default: sharp } = await import("sharp"));
  } catch {
    console.error(
      "✗ sharp is not available.\n" +
        "  It ships as an optional transitive dependency of next, so a\n" +
        "  `npm ci --omit=optional` will drop it. Install it explicitly:\n" +
        "      npm i -D sharp\n",
    );
    process.exit(1);
  }

  await mkdir(OUT_DIR, { recursive: true });
  let failed = false;

  for (const { name, svg } of VARIANTS) {
    const markup = Buffer.from(poster(svg));

    for (const { ext, encode, budget } of FORMATS) {
      const file = `${name}.${ext}`;
      const buf = await encode(sharp(markup, { density: 144 })).toBuffer();
      await writeFile(path.join(OUT_DIR, file), buf);

      const kb = (buf.length / 1024).toFixed(1);
      const max = budget[name];
      if (buf.length > max) {
        console.error(`✗ ${file} — ${kb} KB exceeds the ${(max / 1024).toFixed(0)} KB budget`);
        failed = true;
      } else {
        console.log(`✓ ${file.padEnd(26)} ${svg.w}x${svg.h}  ${kb} KB`);
      }
    }
  }

  // Keep the desktop SVG on disk as the editable source of truth.
  await writeFile(path.join(process.cwd(), "scripts/media/hero-poster.svg"), poster(VARIANTS[0].svg));

  if (failed) process.exit(1);
}

main();
