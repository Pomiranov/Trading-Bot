#!/usr/bin/env node
/**
 * Keeps components on the design tokens.
 *
 * The system declared six type roles and shipped thirteen rendered sizes,
 * because 128 arbitrary `text-[Npx]` utilities outnumbered token classes 3:1.
 * Same story with colour: 23 inline text-opacity levels against 3 semantic
 * tokens, and the semantic colour classes used zero times. Tokens that nothing
 * consumes are documentation, not a system.
 *
 * A lint rule would be the natural home for this, but eslint-plugin-tailwindcss
 * has no working Tailwind v4 support, so a grep gate is the pragmatic option.
 *
 * Budgets are ratchets: they may go down, never up. To use a size that isn't
 * available, add a role to styles/tokens/typography.css.
 *
 * Run via `npm run check:design`.
 */
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = path.join(process.cwd(), "src/components");

const RULES = [
  {
    id: "arbitrary-font-size",
    // text-[13px] but NOT text-[length:var(--text-caption)]
    pattern: /text-\[\d+(?:\.\d+)?px\]/g,
    budget: 0,
    // NOTE: do not write a `text-[length:var(--text-…)]` example literally here.
    // Tailwind v4 scans every non-ignored file in the project for class
    // candidates, including this one, and a pipe-alternation placeholder gets
    // extracted as a real utility — emitting `font-size: var(--text-a|b|c)`,
    // which is a CSS parse error that takes the whole dev server to a 500.
    hint: "use a token size role: label / caption / body / lead / h3",
  },
  {
    id: "raw-white-alpha",
    // rgba(255,255,255,0.x) inline, bypassing the text/border tokens
    pattern: /rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0?\.\d+\s*\)/g,
    // Ratcheted 12 → 6 when the palette went monochrome: the hover/CTA states
    // that used to hand-roll a white alpha now go through --color-highlight-*,
    // --color-fill-subtle and --shadow-cta-*.
    budget: 6,
    hint: "use --color-text-{secondary,tertiary,quaternary} or --color-border[-strong]",
  },
  {
    id: "orange-accent",
    // Both retired oranges: the pre-rebrand #ff8a1e and the #ff7a1a that
    // replaced it. The palette is strictly monochrome now — --color-accent is
    // white — so any orange literal is a regression, in hex or in rgba form.
    pattern: /#ff8a1e|#ff7a1a|255\s*,\s*138\s*,\s*30|255\s*,\s*122\s*,\s*26/gi,
    budget: 0,
    hint: "the palette is monochrome: use --color-accent (white) or a text/border token",
  },
  {
    id: "cyan-as-ink",
    /**
     * The cold blue is *light*, not ink. It is allowed in `box-shadow`, in a
     * `radial-gradient`, and as an SVG `stroke` on decorative geometry — see
     * the doctrine at the top of styles/tokens/color.css.
     *
     * This rule blocks the two ways it would become a hue in the palette:
     * painting text with it, and filling a surface with it. Both are how a
     * restrained signal glow turns into crypto-neon one component at a time.
     *
     * `border-*` is deliberately NOT matched: a 1px cold edge on a route card's
     * hover state is decorative geometry, which is permitted. A border on a
     * *text container* is not, and that one is a review call rather than
     * something a regex can tell apart.
     */
    pattern:
      /(?:text|bg|from|via|to|decoration|caret|accent)-\[color:var\(--color-signal[a-z-]*\)\]|(?<!-)\bcolor:\s*var\(--color-signal|backgroundColor:\s*["'`]?\s*var\(--color-signal|(?:color|background|backgroundColor):\s*["'`]?\s*#(?:7cc8ff|b8e3ff)/gi,
    budget: 0,
    hint: "cold blue is light, not ink: box-shadow / radial-gradient / SVG stroke only — never a text or fill colour",
  },
  {
    id: "purple-gradient",
    // Explicitly out of the direction. Cheap insurance against a stray
    // shadcn/Tailwind default or a copied snippet reintroducing one.
    pattern: /#(?:8b5cf6|a855f7|7c3aed|6d28d9|bf5af2)\b|\b(?:violet|purple|fuchsia)-\d{3}\b/gi,
    budget: 0,
    hint: "no purple anywhere in this palette",
  },
  {
    id: "inline-font-size-style",
    // style={{ fontSize: "10px" }}
    pattern: /fontSize:\s*["'`]\d+(?:\.\d+)?px["'`]/g,
    budget: 0,
    hint: "use a token class instead of an inline fontSize",
  },
];

/** Files allowed to break a rule, with the reason. */
const EXEMPT = new Map([
  [
    "sections/dashboard/dashboard-colors.ts",
    "quotes the product dashboard's own palette by design",
  ],
]);

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (/\.(tsx?|css)$/.test(entry.name)) yield full;
  }
}

async function main() {
  const counts = new Map(RULES.map((r) => [r.id, 0]));
  const sites = new Map(RULES.map((r) => [r.id, []]));

  for await (const file of walk(ROOT)) {
    const rel = path.relative(ROOT, file);
    if (EXEMPT.has(rel)) continue;

    const source = await readFile(file, "utf8");
    const lines = source.split("\n");

    for (const rule of RULES) {
      lines.forEach((line, i) => {
        const matches = line.match(rule.pattern);
        if (!matches) return;
        counts.set(rule.id, counts.get(rule.id) + matches.length);
        sites.get(rule.id).push(`${rel}:${i + 1}  ${matches.join(" ")}`);
      });
    }
  }

  let failed = false;
  for (const rule of RULES) {
    const n = counts.get(rule.id);
    if (n > rule.budget) {
      failed = true;
      console.error(`✗ ${rule.id}: ${n} occurrence(s), budget ${rule.budget}`);
      console.error(`  → ${rule.hint}`);
      for (const site of sites.get(rule.id).slice(0, 20)) console.error(`    ${site}`);
      const extra = sites.get(rule.id).length - 20;
      if (extra > 0) console.error(`    …and ${extra} more`);
    } else {
      console.log(`✓ ${rule.id.padEnd(24)} ${n}/${rule.budget}`);
    }
  }

  if (failed) {
    console.error("\nDesign token check failed.");
    process.exit(1);
  }
}

main();
