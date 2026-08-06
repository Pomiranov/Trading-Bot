#!/usr/bin/env node
/**
 * Behavioural regression assertions for the landing page, run against a live dev
 * or preview server on http://localhost:3000.
 *
 *   node scripts/landing-assertions.mjs [--engine=chromium|webkit]
 *
 * ── Why this exists alongside visual-qa.mjs ──
 *
 * `visual-qa.mjs` is a *probe*: it exports a payload for an agent's Playwright
 * session to evaluate, and it reports numbers. This is a *gate*: it drives the
 * browser itself, exercises the interactions, and exits non-zero. The two are
 * complementary and neither replaces the other.
 *
 * Every check here corresponds to a defect that was measured on this page, not to
 * a general best practice. Read the group headers for what each one is guarding:
 *
 *   1  horizontal overflow / console errors — the site's recurring layout failure
 *   2  one button system — a per-section CTA variant had drifted back in, with a
 *      contour at 2px and a 0.75-alpha cold sheen that read as a blue fill
 *   3  the assistant's hover label surviving a close, because the rule keyed off
 *      `:focus-within` and closing restores focus to the orb
 *   4  the Telegram card's 80px of engineered void, and zero CLS on the demo press
 *   5  the guarantee pair's one-sided 2px white rule and its cold hover
 *   6  1408px of grey transition band, and the seam at each of its eight edges
 *   7  deep links landing behind the sticky header
 *   8  reduced motion — the moving perimeter must stop, the contour must not
 *   9  focus-visible, and the double ring that arc-on-focus produced
 *  10  the palette floor: cold blue as ink, pure white as a surface, purple
 *  11  hover state sticking after a tap
 *  12  the mobile menu's CTA and the form's submit staying on the primitive
 *  13  RU/EN parity of the whole interaction system
 *
 * ── Playwright is deliberately not a dependency ──
 *
 * Same trade `visual-qa.mjs` documents: adding a test runner plus a ~400MB browser
 * download to gate thirteen groups of checks is heavier than the checks warrant,
 * and the alternative — these numbers living only in a chat transcript — is worse
 * than either. So the import is resolved at runtime from whichever install is
 * available, and the failure message says exactly what to do. Both supported
 * routes:
 *
 *   QA_PLAYWRIGHT=/path/to/node_modules/playwright npm run qa:landing
 *   (or install it here: npm i -D playwright && npx playwright install)
 *
 * Both engines matter and both should be run: the contour, the card rim and the
 * band grid are all `mask-composite` constructions, and WebKit needs the
 * `-webkit-` twin of every one of them. `@starting-style` is the one feature
 * WebKit lacks (the assistant panel's entrance), and its absence is a documented
 * progressive-enhancement fallback rather than a failure.
 *
 * Not wired into `npm run check`: that gate must stay dependency-free and must not
 * need a live server.
 */
const pw = await (async () => {
  /* `createRequire().resolve` rather than a bare `import(spec)`: a directory path —
     which is what QA_PLAYWRIGHT naturally is — is not a valid ESM specifier, so a
     dynamic import of it fails with ERR_MODULE_NOT_FOUND even when the package is
     right there. CJS resolution reads the package's `main` for us, and Node can
     import the resulting CJS entry point directly. */
  const { createRequire } = await import("node:module");
  const { pathToFileURL } = await import("node:url");
  const require = createRequire(import.meta.url);
  for (const spec of [process.env.QA_PLAYWRIGHT, "playwright", "playwright-core"]) {
    if (!spec) continue;
    try {
      return await import(pathToFileURL(require.resolve(spec)).href);
    } catch {
      /* try the next one */
    }
  }
  console.error(
    "playwright could not be resolved from this package.\n\n" +
      "  Point at an existing install:\n" +
      "    QA_PLAYWRIGHT=/abs/path/to/node_modules/playwright npm run qa:landing\n\n" +
      "  Or install it here:\n" +
      "    npm i -D playwright && npx playwright install chromium webkit\n",
  );
  process.exit(2);
})();
/* Playwright's entry point is CJS. Node's ESM/CJS bridge can usually hoist named
   exports, but only when it can statically detect them — for a file reached through
   a resolved absolute path it lands everything on `default` instead. Read both. */
const { chromium, webkit } = pw.chromium ? pw : pw.default;

const engineArg = (process.argv.find((a) => a.startsWith("--engine=")) ?? "--engine=chromium").split("=")[1];
const engine = engineArg === "webkit" ? webkit : chromium;
const BASE = "http://localhost:3000";
const VPS = [
  { w: 320, h: 800 }, { w: 360, h: 800 }, { w: 390, h: 844 }, { w: 430, h: 932 },
  { w: 768, h: 1024 }, { w: 1024, h: 768 }, { w: 1280, h: 800 },
  { w: 1440, h: 900 }, { w: 1728, h: 1117 }, { w: 1920, h: 1080 }, { w: 2560, h: 1440 },
];

let pass = 0, fail = 0;
const ok = (name, cond, detail = "") => {
  if (cond) { pass++; console.log(`  ✓ ${name}${detail ? "  " + detail : ""}`); }
  else { fail++; console.log(`  ✗ ${name}  ${detail}`); }
};

const browser = await engine.launch();

// ─────────────────────────────────────────────────────────────────────────────
// 1. No horizontal overflow, no console errors, at every viewport × both locales
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 1. overflow + console, 11 viewports × 2 locales`);
for (const locale of ["ru", "en"]) {
  for (const vp of VPS) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    const errs = [];
    page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
    page.on("pageerror", (e) => errs.push("PAGEERROR " + e.message));
    const res = await page.goto(`${BASE}/${locale}`, { waitUntil: "networkidle" });
    await page.evaluate(async () => {
      window.scrollTo(0, document.documentElement.scrollHeight);
      await new Promise((r) => setTimeout(r, 500));
      window.scrollTo(0, 0);
      await new Promise((r) => setTimeout(r, 300));
    });
    const m = await page.evaluate(() => ({
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      wide: [...document.querySelectorAll("body *")]
        .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.right > document.documentElement.clientWidth + 1 && !el.closest("[data-lenis-prevent-horizontal],.overflow-x-auto"); })
        .slice(0, 3).map((el) => el.tagName + "." + String(el.className).slice(0, 30)),
      h: document.documentElement.scrollHeight,
    }));
    ok(`${locale}/${vp.w} status+overflow+console`, res.status() === 200 && m.over === 0 && errs.length === 0,
      `status=${res.status()} over=${m.over} h=${m.h} ${m.wide.length ? JSON.stringify(m.wide) : ""} ${errs.length ? JSON.stringify(errs.slice(0, 2)) : ""}`);
    await ctx.close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Buttons: one system, no orphans, no stuck state, contour geometry
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 2. button system`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.evaluate(async () => { window.scrollTo(0, document.documentElement.scrollHeight); await new Promise((r) => setTimeout(r, 800)); window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 400)); });

  const inv = await page.evaluate(() => {
    const isCta = (el) =>
      el.matches("a, button") &&
      !el.closest("[role='tablist']") &&
      !el.closest("nav") &&
      !el.closest("details > summary") &&
      (el.classList.contains("btn-liquid-glass"));
    const ctas = [...document.querySelectorAll("a, button")].filter(isCta);
    return {
      total: ctas.length,
      // Every faced CTA must be on the shared lens architecture.
      unlensed: ctas.filter((e) => {
        const cs = getComputedStyle(e);
        const hasFace = cs.backgroundColor !== "rgba(0, 0, 0, 0)";
        return hasFace && !e.classList.contains("btn-lens-face");
      }).map((e) => (e.textContent || "").trim().slice(0, 22)),
      // No per-section variant classes may reappear.
      perSection: ctas.filter((e) => /btn-tier|btn-pricing|btn-hero|btn-access/.test(e.className)).map((e) => (e.textContent || "").trim().slice(0, 22)),
      // Contour geometry must be identical across every faced CTA.
      geom: [...new Set(ctas.filter((e) => e.classList.contains("btn-lens-light")).map((e) => {
        const b = getComputedStyle(e, "::before");
        return `${b.paddingTop}|${b.insetBlockStart}|${getComputedStyle(e).borderRadius}`;
      }))],
      radii: [...new Set(ctas.map((e) => getComputedStyle(e).borderRadius))],
      /* Touch-target floor: 44px for anything a finger can reach.
         Computed height rather than `getBoundingClientRect()`: the rect is scaled
         by every ancestor transform, and two of these controls have one — the
         retracted header shell scales 0.94, and a card mid-`Reveal` has its own.
         The CSS box is what a finger has to hit, and it is transform-independent. */
      short: ctas.filter((e) => { const h = parseFloat(getComputedStyle(e).height); return h > 0 && h < 44; })
        .map((e) => (e.textContent || "").trim().slice(0, 18) + "=" + getComputedStyle(e).height),
    };
  });
  ok("all faced CTAs use the shared lens", inv.unlensed.length === 0, JSON.stringify(inv.unlensed));
  ok("no per-section button variant", inv.perSection.length === 0, JSON.stringify(inv.perSection));
  ok("one contour geometry for every light CTA", inv.geom.length === 1, JSON.stringify(inv.geom));
  ok("contour is 1px", inv.geom.every((g) => g.startsWith("1px")), JSON.stringify(inv.geom));
  ok("CTA count / radii", inv.total >= 8 && inv.radii.length <= 2, `n=${inv.total} radii=${JSON.stringify(inv.radii)}`);
  ok("no CTA under the 44px touch floor", inv.short.length === 0, JSON.stringify(inv.short));

  // Hover → leave must fully reset every pricing CTA
  const stuck = [];
  for (let i = 1; i <= 3; i++) {
    const el = page.locator(`#pricing li:nth-child(${i}) a.btn-liquid-glass`).first();
    const y = await el.evaluate((n) => n.getBoundingClientRect().top + window.scrollY);
    await page.evaluate((y) => window.scrollTo({ top: y - 300, behavior: "instant" }), y);
    await page.waitForTimeout(500);
    await el.hover();
    await page.waitForTimeout(600);
    const on = await el.evaluate((n) => ({ img: getComputedStyle(n).backgroundImage, arc: getComputedStyle(n, "::before").opacity }));
    await page.mouse.move(1400, 60);
    await page.waitForTimeout(700);
    const off = await el.evaluate((n) => ({ img: getComputedStyle(n).backgroundImage, arc: getComputedStyle(n, "::before").opacity }));
    if (on.img === "none" || on.arc !== "1") stuck.push(`tier${i}: hover did not light (${on.arc})`);
    if (off.img !== "none" || off.arc !== "0") stuck.push(`tier${i}: still lit after leave (${off.arc}, ${off.img.slice(0, 24)})`);
  }
  ok("pricing CTAs light on hover and fully reset on leave", stuck.length === 0, JSON.stringify(stuck));

  // The sheen must be a light, not a fill: alpha well under the 0.5 that reads as a tint.
  const sheen = await page.evaluate(() => {
    const el = document.querySelector("#pricing a.btn-liquid-glass");
    return getComputedStyle(el).getPropertyValue("--btn-sheen-a").trim();
  });
  ok("sheen alpha is a light, not a fill", parseFloat(sheen) > 0 && parseFloat(sheen) <= 0.3, `--btn-sheen-a=${sheen}`);

  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Assistant state machine
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 3. assistant`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.evaluate(() => window.scrollTo(0, 1400));
  await page.waitForTimeout(600);
  const read = () => page.evaluate(() => ({
    hint: getComputedStyle(document.querySelector(".assistant-dock__hint")).opacity,
    expanded: document.querySelector(".assistant-orb").getAttribute("aria-expanded"),
    hidden: document.querySelector(".assistant-panel").hasAttribute("hidden"),
    controls: document.querySelector(".assistant-orb").getAttribute("aria-controls"),
    controlsResolves: !!document.getElementById(document.querySelector(".assistant-orb").getAttribute("aria-controls")),
    active: document.activeElement?.className?.toString().slice(0, 24),
  }));
  const orb = page.locator(".assistant-orb");

  ok("rest: label hidden, aria-expanded=false, panel hidden", await read().then((s) => s.hint === "0" && s.expanded === "false" && s.hidden === true), JSON.stringify(await read()));
  ok("aria-controls resolves to a real element", (await read()).controlsResolves);

  await orb.hover(); await page.waitForTimeout(400);
  ok("hover: label visible", (await read()).hint === "1");

  await orb.click(); await page.waitForTimeout(500);
  let s = await read();
  ok("open: aria-expanded=true, panel shown, label suppressed", s.expanded === "true" && s.hidden === false && s.hint === "0", JSON.stringify(s));
  ok("open: focus moved into the panel", s.active.includes("assistant-panel"), s.active);

  // close with the × using a mouse, then move the pointer away
  await page.locator(".assistant-panel__close").click();
  await page.mouse.move(1000, 300);
  await page.waitForTimeout(700);
  s = await read();
  ok("after mouse-× close: label gone, aria-expanded=false, panel hidden", s.hint === "0" && s.expanded === "false" && s.hidden === true, JSON.stringify(s));
  ok("after close: focus returned to the orb", s.active.includes("assistant-orb"), s.active);

  // Escape
  await orb.click(); await page.waitForTimeout(400);
  await page.keyboard.press("Escape");
  await page.mouse.move(1000, 300);
  await page.waitForTimeout(600);
  s = await read();
  ok("after Escape: label gone, closed", s.hint === "0" && s.expanded === "false" && s.hidden === true, JSON.stringify(s));

  // outside click
  await orb.click(); await page.waitForTimeout(400);
  await page.mouse.click(900, 400);
  await page.waitForTimeout(600);
  ok("outside click closes", (await read()).hidden === true);

  // exactly one launcher in the page document (the "N" is Next's dev-tools shadow root)
  const triggers = await page.evaluate(() => ({
    orbs: document.querySelectorAll(".assistant-orb").length,
    roundFixed: [...document.querySelectorAll("button")].filter((b) => {
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      return r.width > 30 && Math.abs(r.width - r.height) < 3 && parseFloat(cs.borderRadius) > 20;
    }).length,
    devtools: !!document.querySelector("nextjs-portal"),
  }));
  ok("exactly one assistant trigger in the page document", triggers.orbs === 1 && triggers.roundFixed === 1,
    `orbs=${triggers.orbs} roundFixed=${triggers.roundFixed} nextjs-portal=${triggers.devtools}`);

  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Telegram: no engineered void, and no CLS on press
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 4. telegram card`);
for (const vp of [{ w: 1440, h: 900 }, { w: 768, h: 1024 }, { w: 390, h: 844 }, { w: 320, h: 800 }]) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.locator("#telegram").scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  const slack = () => page.evaluate(() => {
    const card = document.querySelector("#telegram [data-slot='surface'] [data-slot='surface']");
    const kids = [...card.children];
    const last = kids[kids.length - 1].getBoundingClientRect();
    const cr = card.getBoundingClientRect();
    const padB = parseFloat(getComputedStyle(card).paddingBottom);
    return { h: Math.round(cr.height), slack: Math.round(cr.bottom - last.bottom - padB), padB };
  });
  const before = await slack();
  ok(`${vp.w}: no artificial empty height under the controls`, before.slack <= 2, `slack=${before.slack}px cardH=${before.h}`);

  // press → the card must not change height, and nothing below it may move.
  // Document-relative, not viewport-relative: the focus hand-off calls `.focus()`
  // on the counterpart control, and focusing an element scrolls it into view — so a
  // viewport-relative reading of #faq moves even when the layout is stable.
  const y0 = await page.evaluate(() => document.querySelector("#faq").getBoundingClientRect().top + window.scrollY);
  await page.locator("#telegram button.btn-liquid-glass:visible").first().click();
  await page.waitForTimeout(500);
  const after = await slack();
  const y1 = await page.evaluate(() => document.querySelector("#faq").getBoundingClientRect().top + window.scrollY);
  ok(`${vp.w}: pressing the demo does not reflow the page`, Math.abs(after.h - before.h) <= 2 && Math.abs(y1 - y0) <= 2,
    `h ${before.h}→${after.h}, #faq moved ${Math.round(y1 - y0)}px`);
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Guarantee cards: neutral, symmetric, no cold rim
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 5. guarantee cards`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.locator(".card-neutral").first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  const cards = await page.evaluate(() =>
    [...document.querySelectorAll(".card-neutral")].map((c) => {
      const cs = getComputedStyle(c);
      const after = getComputedStyle(c, "::after");
      const sides = ["Top", "Right", "Bottom", "Left"].map((s) => cs[`border${s}Width`] + " " + cs[`border${s}Color`]);
      return { uniform: new Set(sides).size === 1, sides, rim: after.backgroundImage, shadow: cs.boxShadow };
    }),
  );
  ok("both cards have a uniform border on all four sides", cards.every((c) => c.uniform), JSON.stringify(cards.map((c) => c.sides[0] + " / " + c.sides[3])));
  ok("idle rim carries no saturated cyan", cards.every((c) => !/124,\s*200,\s*255/.test(c.rim)), cards[0].rim.slice(0, 70));

  const el = page.locator(".card-neutral").first();
  await el.hover();
  await page.waitForTimeout(700);
  const hov = await el.evaluate((c) => ({
    rim: getComputedStyle(c, "::after").backgroundImage,
    shadow: getComputedStyle(c).boxShadow,
    border: getComputedStyle(c).borderTopColor + " | " + getComputedStyle(c).borderLeftColor,
    uniform: new Set(["Top", "Right", "Bottom", "Left"].map((s) => getComputedStyle(c)[`border${s}Width`] + getComputedStyle(c)[`border${s}Color`])).size === 1,
    transform: getComputedStyle(c).transform,
  }));
  ok("hover: no cyan anywhere on the card", !/124,\s*200,\s*255/.test(hov.rim) && !/124,\s*200,\s*255/.test(hov.shadow), hov.shadow.slice(0, 60));
  ok("hover: border stays uniform (white highlight, not a one-sided bar)", hov.uniform, hov.border);
  ok("hover: no movement toward the cursor", hov.transform === "none" || hov.transform === "matrix(1, 0, 0, 1, 0, 0)", hov.transform);
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. Band transitions: compact, seamless, continuous grid
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 6. band transitions`);
for (const vp of [{ w: 1440, h: 900 }, { w: 768, h: 1024 }, { w: 390, h: 844 }]) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const bands = await page.evaluate(() =>
    [...document.querySelectorAll(".band-blend")].map((b) => {
      const r = b.getBoundingClientRect();
      const next = b.nextElementSibling, prev = b.previousElementSibling;
      const nc = getComputedStyle(next), pc = getComputedStyle(prev);
      const ramp = getComputedStyle(b).backgroundImage;
      // The ramp's first and last colour stop must equal the neighbours' grounds,
      // or the boundary shows a 1px seam of the wrong colour.
      const stops = ramp.match(/(rgba?\([^)]+\)|oklab\([^)]+\))/g) ?? [];
      return {
        h: Math.round(r.height),
        firstStop: stops[0], lastStop: stops[stops.length - 1],
        nextBg: nc.backgroundColor, prevBg: pc.backgroundColor,
        nextBorderTop: nc.borderTopWidth + " " + nc.borderTopColor,
        gridLayers: b.querySelectorAll(".band-blend__grid").length,
      };
    }),
  );
  const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const norm = (c) => (c === "rgba(0, 0, 0, 0)" ? bodyBg : c);
  ok(`${vp.w}: band height compact`, bands.every((b) => b.h <= (vp.w >= 1024 ? 208 : vp.w >= 640 ? 160 : 128)), JSON.stringify(bands.map((b) => b.h)));
  ok(`${vp.w}: band ≤ 25% of viewport`, bands.every((b) => b.h / vp.h <= 0.25), `max=${Math.max(...bands.map((b) => b.h))} vp=${vp.h}`);
  ok(`${vp.w}: ramp endpoints match both neighbours (no seam)`,
    bands.every((b) => b.firstStop === norm(b.prevBg) && b.lastStop === norm(b.nextBg)),
    JSON.stringify(bands.map((b) => `${b.firstStop}~${norm(b.prevBg)} / ${b.lastStop}~${norm(b.nextBg)}`)));
  ok(`${vp.w}: no visible border drawn on the seam`, bands.every((b) => b.nextBorderTop.includes("rgba(0, 0, 0, 0)") || b.nextBorderTop.startsWith("0px")), JSON.stringify(bands.map((b) => b.nextBorderTop)));
  ok(`${vp.w}: the grid crosses every band`, bands.every((b) => b.gridLayers === 2));
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. Anchors clear the sticky header
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 7. anchors vs sticky header`);
for (const vp of [{ w: 1440, h: 900 }, { w: 768, h: 1024 }, { w: 390, h: 844 }]) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const bad = [];
  for (const id of ["dashboard", "how-it-works", "foundation", "safety", "telegram", "pricing", "faq", "access"]) {
    await page.goto(`${BASE}/ru#${id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const r = await page.evaluate((id) => {
      const s = document.getElementById(id);
      // The first element that actually paints text.
      const first = [...s.querySelectorAll("p,h2,h3,h4,li,dt,span")].find((e) => {
        const b = e.getBoundingClientRect();
        return b.height > 0 && (e.textContent || "").trim().length > 1 && getComputedStyle(e).visibility !== "hidden";
      });
      const shell = document.querySelector(".nav-shell");
      return { top: first ? Math.round(first.getBoundingClientRect().top) : null, shellBottom: shell ? Math.round(shell.getBoundingClientRect().bottom) : 0 };
    }, id);
    if (r.top === null || r.top < r.shellBottom || r.top < 0) bad.push(`${id}: first=${r.top} shellBottom=${r.shellBottom}`);
  }
  ok(`${vp.w}: every deep link lands clear of the header`, bad.length === 0, JSON.stringify(bad));
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. Reduced motion
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 8. reduced motion`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.evaluate(async () => { window.scrollTo(0, document.documentElement.scrollHeight); await new Promise((r) => setTimeout(r, 600)); window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 400)); });
  const el = page.locator("#hero a.btn-liquid-glass").first();
  await el.hover();
  await page.waitForTimeout(500);
  const st = await el.evaluate((n) => ({
    arcAnim: getComputedStyle(n, "::before").animationName,
    arcOpacity: getComputedStyle(n, "::before").opacity,
    sheenAnim: getComputedStyle(n).animationName,
    faceAnimCount: getComputedStyle(n).animationIterationCount,
  }));
  ok("reduced motion: moving perimeter is off, contour still lit", st.arcAnim === "none" && st.arcOpacity === "1", JSON.stringify(st));
  ok("reduced motion: sheen does not wander", st.sheenAnim === "none" || st.faceAnimCount === "1", JSON.stringify(st));
  const hidden = await page.evaluate(() => [...document.querySelectorAll("[data-reveal]")].filter((e) => getComputedStyle(e).opacity === "0").length);
  ok("reduced motion: nothing left invisible by a reveal", hidden === 0, `hidden=${hidden}`);
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 9. Keyboard + focus-visible
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 9. keyboard`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const seen = [];
  let ctaFocus = null;
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const s = await page.evaluate(() => {
      const a = document.activeElement;
      if (!a || a === document.body) return null;
      const cs = getComputedStyle(a);
      return {
        tag: a.tagName, cls: a.className.toString().slice(0, 30),
        fv: a.matches(":focus-visible"),
        outline: cs.outlineWidth + " " + cs.outlineStyle,
        isCta: a.classList.contains("btn-liquid-glass"),
        arc: a.classList.contains("btn-lens-light") ? getComputedStyle(a, "::before").opacity : null,
      };
    });
    if (!s) break;
    seen.push(s);
    if (s.isCta && !ctaFocus) ctaFocus = s;
  }
  ok("tab order reaches a CTA", !!ctaFocus, ctaFocus ? JSON.stringify(ctaFocus) : "none");
  ok("focused CTA gets a real outline", !!ctaFocus && ctaFocus.fv && parseFloat(ctaFocus.outline) >= 2, ctaFocus ? ctaFocus.outline : "");
  ok("focused light CTA does not also light the arc (no double ring)", !ctaFocus || ctaFocus.arc === "0" || ctaFocus.arc === null, ctaFocus ? `arc=${ctaFocus.arc}` : "");
  ok("every focused element is focus-visible (no trap / no invisible focus)", seen.every((s) => s.fv || s.outline !== "0px none"), JSON.stringify(seen.filter((s) => !s.fv).slice(0, 3)));
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 10. Palette floor — nothing turned cyan-as-ink or pure white on paper
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 10. palette`);
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.evaluate(async () => { window.scrollTo(0, document.documentElement.scrollHeight); await new Promise((r) => setTimeout(r, 600)); window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 300)); });
  const p = await page.evaluate(() => {
    const cyanInk = [], pureWhiteSurface = [], purple = [];
    const m = (s) => (s.match(/[\d.]+/g) || []).map(Number);
    for (const el of document.querySelectorAll("body *")) {
      const cs = getComputedStyle(el);
      const r0 = el.getBoundingClientRect();

      /* ── "ink" means text, so only elements that actually paint a glyph count ──
         `color` also feeds `currentColor`, which is how the grid backplates draw
         their hairlines — decorative geometry, and a permitted use of the signal
         colour. Testing `color` alone flagged `.signal-field__grid`, an element
         with no text in it at all. Own text nodes only. */
      const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
      if (ownText) {
        const [r, g, b] = m(cs.color);
        // Cold blue as a text colour. Green/red are the permitted trade
        // semantics, so require blue to dominate *both* other channels.
        if (b > r + 40 && b > g + 20 && b > 150 && r < 200) cyanInk.push(el.tagName + "." + String(el.className).slice(0, 24) + " " + cs.color);
        if (b > 150 && r > 110 && g < r - 40 && g < b - 40) purple.push(el.tagName + " ink " + cs.color);
      }

      const bg = m(cs.backgroundColor);
      const opaque = bg.length < 4 || bg[3] === 1;
      /* ── A *surface*, not a control ──
         The primary CTA is deliberately a pure-white pill: white is the accent,
         and black-on-white is the page's 20.4:1 anchor. The rule the palette
         doctrine states is about light *surfaces* — sections, bands, panels — not
         about a 44px control. So this only looks at objects large enough to be a
         surface. */
      if (opaque && bg[0] === 255 && bg[1] === 255 && bg[2] === 255 && r0.width > 220 && r0.height > 120)
        pureWhiteSurface.push(el.tagName + "." + String(el.className).slice(0, 24) + ` ${Math.round(r0.width)}×${Math.round(r0.height)}`);
      if (opaque && bg[0] > 120 && bg[2] > 180 && bg[1] < bg[0] - 40 && bg[1] < bg[2] - 40) purple.push(el.tagName + " fill " + cs.backgroundColor);
    }
    return { cyanInk: cyanInk.slice(0, 4), pureWhiteSurface: pureWhiteSurface.slice(0, 4), purple: purple.slice(0, 4), paper: getComputedStyle(document.querySelector("#foundation")).backgroundColor };
  });
  ok("no cold blue used as text ink", p.cyanInk.length === 0, JSON.stringify(p.cyanInk));
  ok("no pure #ffffff surface (controls excepted)", p.pureWhiteSurface.length === 0, JSON.stringify(p.pureWhiteSurface));
  ok("no purple/violet ink or fill", p.purple.length === 0, JSON.stringify(p.purple));
  ok("paper is a warm mineral off-white, not white", p.paper === "rgb(228, 225, 218)", p.paper);
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 11. Touch: nothing sticks after a tap
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 11. touch`);
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: engineArg !== "webkit" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.locator("#pricing").scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  const cta = page.locator("#pricing a.btn-liquid-glass").first();
  const before = await cta.evaluate((n) => ({ img: getComputedStyle(n).backgroundImage, arc: getComputedStyle(n, "::before").opacity }));
  await cta.dispatchEvent("touchstart");
  await cta.dispatchEvent("touchend");
  await page.waitForTimeout(600);
  const after = await cta.evaluate((n) => ({ img: getComputedStyle(n).backgroundImage, arc: getComputedStyle(n, "::before").opacity }));
  ok("touch: no sheen and no arc before or after a tap",
    before.img === "none" && after.img === "none" && before.arc === "0" && after.arc === "0",
    JSON.stringify({ before, after }));

  // The hover label must never render on a narrow/touch layout at all.
  const hint = await page.evaluate(() => {
    const h = document.querySelector(".assistant-dock__hint");
    return { display: getComputedStyle(h).display, opacity: getComputedStyle(h).opacity };
  });
  ok("touch: the assistant label is not in the layout", hint.display === "none", JSON.stringify(hint));

  // Card hovers are all gated behind (hover: hover); nothing may be lifted.
  const lifted = await page.evaluate(() =>
    [...document.querySelectorAll(".card-premium")].filter((c) => {
      const t = getComputedStyle(c).transform;
      return t !== "none" && t !== "matrix(1, 0, 0, 1, 0, 0)";
    }).length,
  );
  ok("touch: no card is left in a lifted state", lifted === 0, `lifted=${lifted}`);
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 12. Mobile menu + form controls
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 12. mobile menu + form`);
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ru`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const toggle = page.locator("header button[aria-expanded]").first();
  ok("mobile: a menu toggle exists with aria-expanded", await toggle.count() > 0);
  if (await toggle.count()) {
    await toggle.click();
    await page.waitForTimeout(600);
    const m = await page.evaluate(() => {
      const t = document.querySelector("header button[aria-expanded]");
      const ctas = [...document.querySelectorAll("a.btn-liquid-glass, button.btn-liquid-glass")]
        .filter((e) => e.getBoundingClientRect().width > 0 && e.closest("header"));
      return {
        expanded: t.getAttribute("aria-expanded"),
        ctas: ctas.map((e) => ({ txt: (e.textContent || "").trim().slice(0, 20), h: getComputedStyle(e).height, lens: e.classList.contains("btn-lens-face") })),
      };
    });
    ok("mobile: menu opens (aria-expanded=true)", m.expanded === "true", m.expanded);
    ok("mobile: menu CTA is on the shared lens and ≥44px",
      m.ctas.length > 0 && m.ctas.every((c) => c.lens && parseFloat(c.h) >= 44), JSON.stringify(m.ctas));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    ok("mobile: Escape closes the menu",
      (await page.evaluate(() => document.querySelector("header button[aria-expanded]").getAttribute("aria-expanded"))) === "false");
  }

  // The form's submit control shares the primitive and has a disabled path.
  await page.locator("#access").scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  const submit = await page.evaluate(() => {
    const b = document.querySelector("#access form button[type='submit'], #access form button:not([type])");
    if (!b) return null;
    return { lens: b.classList.contains("btn-lens-face"), h: getComputedStyle(b).height, disabled: b.disabled, opacity: getComputedStyle(b).opacity };
  });
  ok("form submit uses the shared lens at ≥44px", !!submit && submit.lens && parseFloat(submit.h) >= 44, JSON.stringify(submit));
  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// 13. RU/EN parity of the interaction system
// ─────────────────────────────────────────────────────────────────────────────
console.log(`\n[${engineArg}] 13. RU/EN parity`);
{
  const read = async (locale) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto(`${BASE}/${locale}`, { waitUntil: "networkidle" });
    await page.evaluate(async () => { window.scrollTo(0, document.documentElement.scrollHeight); await new Promise((r) => setTimeout(r, 700)); window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 300)); });
    const r = await page.evaluate(() => {
      const ctas = [...document.querySelectorAll("a.btn-liquid-glass, button.btn-liquid-glass")].filter((e) => e.getBoundingClientRect().width > 0);
      return {
        sections: [...document.querySelectorAll("section[id]")].map((s) => s.id).join(","),
        ctaCount: ctas.length,
        lensedAll: ctas.filter((e) => getComputedStyle(e).backgroundColor !== "rgba(0, 0, 0, 0)").every((e) => e.classList.contains("btn-lens-face")),
        arcGeom: [...new Set(ctas.filter((e) => e.classList.contains("btn-lens-light")).map((e) => getComputedStyle(e, "::before").paddingTop))].join("|"),
        neutralCards: document.querySelectorAll(".card-neutral").length,
        bands: document.querySelectorAll(".band-blend").length,
        paper: getComputedStyle(document.querySelector("#foundation")).backgroundColor,
      };
    });
    await ctx.close();
    return r;
  };
  const ru = await read("ru"), en = await read("en");
  ok("section order identical", ru.sections === en.sections, ru.sections);
  ok("same number of CTAs", ru.ctaCount === en.ctaCount, `ru=${ru.ctaCount} en=${en.ctaCount}`);
  ok("every faced CTA lensed in both locales", ru.lensedAll && en.lensedAll);
  ok("identical contour geometry in both locales", ru.arcGeom === en.arcGeom && ru.arcGeom === "1px", `ru=${ru.arcGeom} en=${en.arcGeom}`);
  ok("neutral cards / bands / paper identical", ru.neutralCards === en.neutralCards && ru.bands === en.bands && ru.paper === en.paper,
    JSON.stringify({ ru: [ru.neutralCards, ru.bands, ru.paper], en: [en.neutralCards, en.bands, en.paper] }));
}

await browser.close();
console.log(`\n[${engineArg}] ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
