#!/usr/bin/env node
/**
 * Visual/behavioural QA for the landing page, run against a live dev or preview
 * server across both locales and four viewports.
 *
 * ── Why this is a script and not a Playwright test suite ──
 *
 * Playwright is not a dependency of this package, and adding a full test runner
 * plus its browser download to check thirteen invariants is a heavier
 * commitment than the checks warrant. This drives whatever Chromium is already
 * available through the CDP endpoint of a running browser, or — the normal
 * path — is executed by an agent's Playwright session, which passes `page` in.
 *
 * It is committed because the alternative is that these numbers live only in a
 * chat transcript. Every threshold here corresponds to a defect that was
 * measured on this page, not to a general best practice:
 *
 *   • horizontal overflow — the site's recurring layout failure
 *   • backward scroll     — the worst historical bug, caused by two things
 *                           reading scroll position at once
 *   • cursor affordance   — 4 cards contained a link and were not pointer
 *                           targets
 *   • anchor landing      — 5 of 10 nav targets dropped the reader onto a third
 *                           of a screen of empty space
 *   • contrast            — the paper bands are a new surface and none of the
 *                           ratios measured against #030303 carry over
 *   • honesty             — the page must contain no result figure, ever
 *
 * Usage: node scripts/visual-qa.mjs [baseUrl]
 */

export const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1024, height: 800 },
  { name: "tablet", width: 768, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

export const LOCALES = ["ru", "en"];

/** Nav targets that must land cleanly when clicked. */
export const ANCHORS = [
  "dashboard",
  "how-it-works",
  "foundation",
  "safety",
  "telegram",
  "pricing",
  "faq",
  "access",
];

/**
 * Terms that must never appear as a *published figure* on this page.
 *
 * Matched against rendered text rather than source: the point is what a visitor
 * can actually read.
 *
 * ── Why the adjacency window is tight ──
 *
 * The first version used `\D{0,20}\d`, and it produced a false positive on
 * approved copy. `content/ru/learning-system.mdx` names the *inputs* to the
 * belief updater — "по равновзвешенному среднему из win rate, profit factor и
 * expectancy. До 20 сделок…" — where the `20` is a sample-count constant 22
 * characters further on and no value for any of those terms is published
 * anywhere.
 *
 * Naming a metric the system consumes is not the same as claiming a figure for
 * it, and the site must be able to explain its own mechanism. So the number has
 * to sit immediately after the term, as it would in "Win rate: 62%" or
 * "Profit factor 1.8", and not merely somewhere in the same sentence.
 */
export const FORBIDDEN_CLAIMS = [
  /win\s*rate\W{0,4}\d/i,
  /profit\s*factor\W{0,4}\d/i,
  /sharpe\W{0,4}\d/i,
  /\bdrawdown\W{0,4}\d+\s*%/i,
  /\bROI\W{0,4}\d/i,
  /доходность\W{0,4}\d+\s*%/i,
  /прибыль\W{0,4}[+-]?\d+\s*%/i,
  /винрейт\W{0,4}\d/i,
];

/** The evaluated payload. Kept as a string so it can be handed to page.evaluate. */
export const PROBE = () => {
  const d = document.documentElement;

  // ── contrast helpers (WCAG 2.1) ──
  const lum = (r, g, b) => {
    const f = (c) => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const parse = (s) => {
    const m = (s || "").match(/[\d.]+/g);
    if (!m) return null;
    return { r: +m[0], g: +m[1], b: +m[2], a: m[3] === undefined ? 1 : +m[3] };
  };
  const ratio = (fg, bg) => {
    const c = {
      r: fg.r * fg.a + bg.r * (1 - fg.a),
      g: fg.g * fg.a + bg.g * (1 - fg.a),
      b: fg.b * fg.a + bg.b * (1 - fg.a),
    };
    const L1 = lum(c.r, c.g, c.b);
    const L2 = lum(bg.r, bg.g, bg.b);
    const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1];
    return (hi + 0.05) / (lo + 0.05);
  };
  const effectiveBg = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const p = parse(getComputedStyle(n).backgroundColor);
      if (p && p.a === 1) return p;
      n = n.parentElement;
    }
    return { r: 3, g: 3, b: 3 };
  };

  // ── 1. horizontal overflow ──
  const overflowPx = d.scrollWidth - d.clientWidth;
  const wide = [...document.querySelectorAll("body *")]
    .filter((el) => {
      const r = el.getBoundingClientRect();
      if (r.width === 0) return false;
      if (r.right <= d.clientWidth + 1) return false;
      // A declared horizontal scroller is allowed to be wider than the viewport.
      return !el.closest("[data-lenis-prevent-horizontal],.overflow-x-auto");
    })
    .slice(0, 5)
    .map((el) => el.tagName + "." + String(el.className).slice(0, 40));

  // ── 2. clickable affordance ──
  //
  // A card that contains a navigation link must itself be a pointer target.
  // Baseline: 4 offenders — all three Audience cards and the Access "Live"
  // card, each of which *is* the route selector while only its 12-word arrow
  // link actually navigated.
  //
  // A card whose only link is a rendered *button* is excluded: it already
  // carries an explicit, unambiguous affordance, and making the whole card
  // clickable around a button would give one card two competing targets. The
  // pricing card is the case in point.
  const cursorOffenders = [...document.querySelectorAll('[data-slot="surface"]')]
    .filter((c) => {
      const links = [...c.querySelectorAll("a[href]")];
      return links.length > 0 && !links.every((a) => a.matches(".btn-liquid-glass"));
    })
    .filter((c) => getComputedStyle(c).cursor !== "pointer")
    .map((c) => (c.closest("section")?.id ?? "?") + ": " + (c.textContent || "").trim().slice(0, 30));

  // ── 3. hover/focus language ──
  const surfaces = [...document.querySelectorAll('[data-slot="surface"]')];

  // ── 4. contrast across the whole page ──
  const contrastFails = [];
  const seen = new Set();
  for (const el of document.querySelectorAll("h1,h2,h3,p,li,dd,dt,span,a,code,summary,button,th,td")) {
    const text = (el.textContent || "").trim();
    if (text.length < 2) continue;
    if (!el.offsetParent && getComputedStyle(el).position !== "fixed") continue;
    if ([...el.children].some((c) => (c.textContent || "").trim() === text)) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.opacity === "0") continue;
    const fg = parse(cs.color);
    if (!fg) continue;
    const size = parseFloat(cs.fontSize);
    const key = cs.color + "|" + size + "|" + (el.closest("section")?.id ?? "");
    if (seen.has(key)) continue;
    seen.add(key);
    const cr = ratio(fg, effectiveBg(el));
    const large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight) >= 700);
    const floor = large ? 3 : 4.5;
    if (cr < floor) {
      contrastFails.push({
        section: el.closest("section")?.id ?? "footer",
        color: cs.color,
        size,
        cr: +cr.toFixed(2),
        floor,
        sample: text.slice(0, 30),
      });
    }
  }

  // ── 5. honest content ──
  const bodyText = document.body.innerText;

  // ── 6. structure ──
  const sections = [...document.querySelectorAll("section[id]")].map((s) => ({
    id: s.id,
    h: Math.round(s.getBoundingClientRect().height),
  }));

  return {
    pageHeight: Math.round(d.scrollHeight),
    overflowPx,
    overflowingElements: wide,
    cursorOffenders,
    surfaceCount: surfaces.length,
    contrastFails,
    sections,
    bodyText,
    tabs: {
      count: document.querySelectorAll('[role="tab"]').length,
      inFocusOrder: [...document.querySelectorAll('[role="tab"]')].filter(
        (t) => t.getAttribute("tabindex") === "0",
      ).length,
      panels: document.querySelectorAll('[role="tabpanel"]').length,
    },
    details: document.querySelectorAll("details").length,
    headerCompact: document.querySelector("header")?.dataset.compact,
    revealsHidden: [...document.querySelectorAll("[data-reveal]")].filter(
      (e) => getComputedStyle(e).opacity === "0",
    ).length,
  };
};
