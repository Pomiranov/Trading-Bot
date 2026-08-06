#!/usr/bin/env node
/**
 * Dashboard-side design-token gate.
 *
 * The site has `website/scripts/check-design-tokens.mjs` and its `ROOT` is
 * `src/components`, so `src/app`, `src/lib` and `globals.css` were unguarded on
 * its own side. This is the dashboard's own gate, deliberately separate: extending
 * the site's script would make the terminal's build depend on the marketing site's
 * tooling, and `website/**` is read-only for this work.
 *
 * Two jobs:
 *
 * 1. **Enforce the discipline** — no raw colour outside the token file, no retired
 *    hues, no arbitrary sizes, no infinite animation, no unescaped sink.
 * 2. **Verify provenance** — the surface/text/border/trade values in
 *    `css/tokens.css` are a *copy* of the site's. This reads the site's token file
 *    (read-only) and fails when a value drifts, so the copy cannot silently
 *    diverge from its source.
 *
 * Budgets are ratchets: they may go down, never up.
 *
 * Run: `node bot/ui/static/check-dashboard-tokens.mjs`
 */

import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const REPO = path.resolve(HERE, '../../..');
const CSS_DIR = path.join(HERE, 'css');
const APP_DIR = path.join(HERE, 'app');
const TEMPLATE_DIR = path.resolve(HERE, '../templates');
const SITE_TOKENS = path.join(REPO, 'website/src/styles/tokens/color.css');

/** The token file is the one place raw colour is allowed to appear. */
const TOKEN_FILE = path.join(CSS_DIR, 'tokens.css');

/**
 * The Mini App is a separate document on a separate route with its own design
 * language (it is a game). It is out of the operational palette's scope — what
 * matters is that its stylesheet no longer leaks into the dashboard, which is now
 * structural: the dashboard template does not load it.
 */
const EXCLUDED_DIRS = new Set(['miniapp', 'fonts']);

const RULES = [
  {
    id: 'raw-hex-outside-tokens',
    description: 'Raw hex colour outside css/tokens.css',
    budget: 0,
    // Skips hex inside a data: URI (the favicon) and inside an SVG stroke
    // attribute in a template, both of which are unavoidable.
    pattern: /#[0-9a-f]{3,8}\b/gi,
    appliesTo: (file) => file !== TOKEN_FILE && (file.endsWith('.css') || file.endsWith('.js')),
    hint: 'add a token to css/tokens.css and reference it with var(--qf-…)',
  },
  {
    id: 'raw-rgba-outside-tokens',
    description: 'Raw rgba() outside css/tokens.css',
    budget: 0,
    pattern: /rgba?\(\s*\d+\s*,/gi,
    appliesTo: (file) => file !== TOKEN_FILE && (file.endsWith('.css') || file.endsWith('.js')),
    hint: 'use --qf-text-*, --qf-border[-strong], --qf-*-dim',
  },
  {
    id: 'orange-accent',
    description: 'The retired Bitcoin-orange identity, in any form',
    budget: 0,
    // #F7931A and its four relatives, plus the rgba() family.
    pattern: /#f7931a|#e07d0a|#c9701a|#ff9e24|247\s*,\s*147\s*,\s*26|#f7c948/gi,
    appliesTo: () => true,
    hint: 'the accent is white (--qf-accent); warning is --qf-warning',
  },
  {
    id: 'purple',
    description: 'Purple has no semantic meaning in this product',
    budget: 0,
    pattern: /#8b5cf6|#a855f7|#7c3aed|#6d28d9|\b(?:violet|purple|fuchsia)-\d{3}\b/gi,
    appliesTo: () => true,
    hint: 'remove it',
  },
  {
    id: 'saturated-blue-cyan-as-ink',
    description: 'Cold blue is light, not ink',
    budget: 0,
    // The retired ink blues, plus any attempt to use the signal colour as a
    // text or background value. `box-shadow`, `radial-gradient` and SVG `stroke`
    // are permitted and are deliberately not matched.
    pattern: /#3861fb|#06b6d4|#00c076|#f6465d|(?:^|[^-])color:\s*var\(--qf-signal|background(?:-color)?:\s*var\(--qf-signal/gim,
    appliesTo: () => true,
    hint: 'cold blue only as stroke or shadow at ≤0.28 alpha, on sign-in and empty states',
  },
  {
    id: 'orbitron',
    description: 'Orbitron — a sci-fi display face against an institutional brand',
    budget: 0,
    pattern: /orbitron/gi,
    appliesTo: (file) => !file.includes('miniapp'),
    hint: 'Geist and Geist Mono only',
  },
  {
    id: 'google-fonts-runtime',
    description: 'A runtime request to Google Fonts',
    budget: 0,
    pattern: /fonts\.googleapis\.com|fonts\.gstatic\.com/gi,
    appliesTo: (file) => !file.includes('miniapp'),
    hint: 'fonts are self-hosted in static/fonts',
  },
  {
    id: 'cdn-script',
    description: 'A third-party script on the critical path',
    budget: 0,
    pattern: /unpkg\.com|cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com/gi,
    appliesTo: (file) => !file.includes('miniapp'),
    hint: 'charts are local SVG; nothing else needs a CDN',
  },
  {
    id: 'infinite-animation',
    description: 'An unbounded animation',
    budget: 0,
    // `animation-iteration-count: 1 !important` inside the reduced-motion block
    // is the fix, not a violation, so only `infinite` is matched.
    pattern: /animation[^;{}]*\binfinite\b|animation-iteration-count:\s*infinite/gi,
    appliesTo: (file) => file.endsWith('.css'),
    hint: 'bound every loop; nothing pulses on a healthy state',
  },
  {
    id: 'inner-html',
    description: 'An innerHTML/outerHTML sink',
    budget: 0,
    pattern: /\.(?:inner|outer)HTML\s*=|insertAdjacentHTML/g,
    appliesTo: (file) => file.endsWith('.js'),
    hint: 'use dom.js: createElement + textContent',
  },
  {
    id: 'inline-event-handler',
    description: 'An inline on* handler in a template',
    budget: 0,
    pattern: /\son(?:click|change|input|submit|load|error|mouseover)\s*=/gi,
    appliesTo: (file) => file.endsWith('.html'),
    hint: 'addEventListener',
  },
  {
    id: 'arbitrary-font-size',
    description: 'A font-size literal outside the six type roles',
    budget: 0,
    // The lookahead must sit *after* the whitespace, not before it: with
    // `\s*(?!var\()` the engine backtracks `\s*` to zero width, tests the
    // lookahead against a space, passes, and then matches the `var(...)` it was
    // supposed to exclude. `[ \t]*` plus an anchored alternation avoids that.
    pattern: /font-size:(?![ \t]*(?:var\(|inherit|initial|unset))[ \t]*[\d.]+(?:px|rem|em)/gi,
    appliesTo: (file) => file.endsWith('.css') && file !== TOKEN_FILE,
    hint: 'use --qf-{label,caption,body,heading,metric,metric-lg}-size',
  },
  {
    id: 'tiny-text',
    description: 'Text below the 12px floor',
    budget: 0,
    pattern: /font-size:[ \t]*(?:[0-9]|1[01])(?:\.\d+)?px/gi,
    appliesTo: (file) => file.endsWith('.css') && file !== TOKEN_FILE,
    hint: '11px is permitted only for the mono label role, declared in tokens.css',
  },
  {
    id: 'arbitrary-radius',
    description: 'A border-radius outside the seven-step scale',
    budget: 0,
    pattern: /border-radius:(?![ \t]*(?:var\(|0\b|50%|1px|2px|inherit|initial))[ \t]*[^;\n]+/gi,
    appliesTo: (file) => file.endsWith('.css') && file !== TOKEN_FILE,
    hint: 'use --qf-radius-{xs,sm,md,lg,xl,2xl,full}',
  },
  {
    id: 'arbitrary-shadow',
    description: 'A box-shadow outside the three defined shadows',
    budget: 0,
    // `inset` shadows are the selected-row and active-nav rules — a border
    // treatment rather than elevation, so they are not part of the shadow budget.
    pattern: /box-shadow:(?![ \t]*(?:var\(|none|inset|inherit|initial))[ \t]*[^;\n]+/gi,
    appliesTo: (file) => file.endsWith('.css') && file !== TOKEN_FILE,
    hint: 'use --qf-shadow-{panel,hover,overlay}',
  },
];

/**
 * Values copied from the site. Read from `website/src/styles/tokens/color.css`
 * at check time, so a drift on either side fails the build.
 */
const PROVENANCE = [
  ['--qf-bg', '--color-bg'],
  ['--qf-bg-elevated', '--color-bg-elevated'],
  ['--qf-surface', '--color-surface'],
  ['--qf-panel', '--color-panel'],
  ['--qf-panel-raised', '--color-panel-raised'],
  ['--qf-graphite', '--color-graphite'],
  ['--qf-border', '--color-border'],
  ['--qf-border-strong', '--color-border-strong'],
  ['--qf-text-primary', '--color-text-primary'],
  ['--qf-text-secondary', '--color-text-secondary'],
  ['--qf-text-tertiary', '--color-text-tertiary'],
  ['--qf-text-quaternary', '--color-text-quaternary'],
  ['--qf-accent', '--color-accent'],
  ['--qf-accent-hover', '--color-accent-hover'],
  ['--qf-success', '--color-success'],
  ['--qf-success-dim', '--color-success-dim'],
  ['--qf-danger', '--color-danger'],
  ['--qf-danger-dim', '--color-danger-dim'],
  ['--qf-neutral', '--color-neutral'],
  ['--qf-paper', '--color-paper'],
  ['--qf-on-paper', '--color-on-paper'],
];

/**
 * Extract custom-property declarations.
 *
 * Comments must be stripped first. Both token files discuss token names in prose
 * — «NOT --color-muted: shadcn's bridge …» — and an unterminated `--name:` inside
 * a comment makes `[^;]+` run past the newline and swallow the *next* real
 * declaration. That is how `--color-neutral` went missing and `--qf-accent`
 * resolved to the forced-colors value.
 *
 * The value is also confined to one line, so a malformed declaration cannot
 * consume its neighbours.
 */
function declarations(source) {
  const map = new Map();
  const clean = source.replace(/\/\*[\s\S]*?\*\//g, '');
  const re = /(--[a-z0-9-]+)\s*:\s*([^;\n]+);/gi;
  let match;
  while ((match = re.exec(clean)) !== null) {
    if (!map.has(match[1])) map.set(match[1], match[2].trim());
  }
  return map;
}

function normalise(value) {
  return value.replace(/\s+/g, '').toLowerCase();
}

async function* walk(dir) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry.name)) continue;
      yield* walk(path.join(dir, entry.name));
    } else if (/\.(css|js|mjs|html)$/.test(entry.name)) {
      yield path.join(dir, entry.name);
    }
  }
}

/** Strip comments so a rule quoted in prose is not counted as a violation. */
function stripComments(source, file) {
  let out = source.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/\S/g, ' '));
  if (file.endsWith('.js') || file.endsWith('.mjs')) {
    out = out.replace(/^\s*\/\/.*$/gm, '');
    out = out.replace(/^\s*\*.*$/gm, '');
  }
  if (file.endsWith('.html')) {
    out = out.replace(/<!--[\s\S]*?-->/g, '');
    out = out.replace(/\{#[\s\S]*?#\}/g, '');
    // The favicon is a data: URI and must carry literal hex.
    out = out.replace(/href="data:image\/svg\+xml[^"]*"/g, 'href="data:"');
  }
  return out;
}

async function main() {
  const counts = new Map(RULES.map((r) => [r.id, 0]));
  const sites = new Map(RULES.map((r) => [r.id, []]));

  const roots = [CSS_DIR, APP_DIR, TEMPLATE_DIR];
  for (const root of roots) {
    for await (const file of walk(root)) {
      const raw = await readFile(file, 'utf8');
      const source = stripComments(raw, file);
      const relative = path.relative(REPO, file);

      for (const rule of RULES) {
        if (!rule.appliesTo(file)) continue;
        source.split('\n').forEach((line, index) => {
          const matches = line.match(rule.pattern);
          if (!matches) return;
          counts.set(rule.id, counts.get(rule.id) + matches.length);
          sites.get(rule.id).push(`${relative}:${index + 1}  ${matches.join(' ')}`);
        });
      }
    }
  }

  let failed = false;
  for (const rule of RULES) {
    const n = counts.get(rule.id);
    if (n > rule.budget) {
      failed = true;
      console.error(`✗ ${rule.id}: ${n} occurrence(s), budget ${rule.budget}`);
      console.error(`  ${rule.description}`);
      console.error(`  → ${rule.hint}`);
      for (const site of sites.get(rule.id).slice(0, 12)) console.error(`    ${site}`);
      const extra = sites.get(rule.id).length - 12;
      if (extra > 0) console.error(`    …and ${extra} more`);
    } else {
      console.log(`✓ ${rule.id.padEnd(30)} ${n}/${rule.budget}`);
    }
  }

  // ── Provenance ───────────────────────────────────────────────────────────
  let siteSource = null;
  try {
    siteSource = await readFile(SITE_TOKENS, 'utf8');
  } catch {
    console.warn('⚠ site token file unavailable — provenance check skipped');
  }

  if (siteSource) {
    const dashboard = declarations(await readFile(TOKEN_FILE, 'utf8'));
    const site = declarations(siteSource);
    const drift = [];
    for (const [ours, theirs] of PROVENANCE) {
      const mine = dashboard.get(ours);
      const source = site.get(theirs);
      if (mine === undefined) { drift.push(`${ours} missing from the dashboard tokens`); continue; }
      if (source === undefined) { drift.push(`${theirs} missing from the site tokens`); continue; }
      if (normalise(mine) !== normalise(source)) {
        drift.push(`${ours} = ${mine} but site ${theirs} = ${source}`);
      }
    }
    if (drift.length) {
      failed = true;
      console.error(`✗ token-provenance: ${drift.length} value(s) drifted from the site`);
      for (const item of drift) console.error(`    ${item}`);
    } else {
      console.log(`✓ ${'token-provenance'.padEnd(30)} ${PROVENANCE.length} values match the site`);
    }
  }

  // ── Budgets that are counts rather than prohibitions ──────────────────────
  // Counted from the declaration map, not by matching the raw text: the
  // forced-colors and prefers-contrast blocks redeclare the same names, and
  // counting occurrences would report six shadows where three exist.
  const tokens = declarations(await readFile(TOKEN_FILE, 'utf8'));
  const radii = new Set();
  const shadowNames = new Set();
  const typeRoles = new Set();
  for (const [name, value] of tokens) {
    if (/^--qf-radius-/.test(name)) radii.add(normalise(value));
    if (/^--qf-shadow-/.test(name)) shadowNames.add(name);
    const role = name.match(/^--qf-([a-z-]+)-size$/);
    // `--qf-root-size` is the rem anchor on <html>, not a type role.
    if (role && role[1] !== 'root') typeRoles.add(role[1]);
  }
  const shadows = shadowNames.size;

  const budgets = [
    ['radii', radii.size, 7],
    ['shadows', shadows, 3],
    ['type-roles', typeRoles.size, 6],
  ];
  for (const [name, value, limit] of budgets) {
    if (value > limit) {
      failed = true;
      console.error(`✗ ${name}: ${value}, budget ${limit}`);
    } else {
      console.log(`✓ ${name.padEnd(30)} ${value}/${limit}`);
    }
  }

  if (failed) {
    console.error('\nDashboard design-token check failed.');
    process.exit(1);
  }
  console.log('\nDashboard design-token check passed.');
}

main();
