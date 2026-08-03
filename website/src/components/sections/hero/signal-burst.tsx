"use client";

import { useEffect, useRef } from "react";

/**
 * The hero's response to a click or a tap: a short, contained dispersal of
 * signal along the panel's own grid.
 *
 * ── The brief, and the two ways it could have been got wrong ──
 *
 * "Controlled signal dispersion inside a premium terminal grid" — not a
 * click-sparkle, not a shockwave, not a glitch. The failure modes are specific
 * enough to design against directly:
 *
 *   • *decoration thrown over the page*. Avoided by making the effect obey
 *     geometry that is already there: the origin snaps to the nearest 64px grid
 *     intersection and every trace runs along a grid axis. A diagonal is not a
 *     line this grid has, so a diagonal would read as something laid on top of
 *     the panel rather than as the panel conducting.
 *
 *   • *a symmetrical cross*. Four equal traces from a point is a plus sign, and
 *     a plus sign is a cursor, not a dispersal. The four traces below have four
 *     different lengths, four different durations and four different delays.
 *
 * ── Why the element pool, and what it guarantees ──
 *
 * Six elements are created once, on mount, and reused for the life of the
 * component. Nothing is ever appended on click.
 *
 * That is the direct answer to "repeated clicks must not accumulate DOM,
 * artefacts or lag": there is no code path here that can grow anything. A
 * hundred clicks cost exactly what one costs, and the effect looks identical on
 * the hundredth — it simply relocates. Each click cancels the animations still
 * running on the pool before restarting them, so two rapid clicks produce one
 * burst at the second position rather than two overlapping bursts.
 *
 * ── Why WAAPI rather than CSS keyframes ──
 *
 * The origin moves per click, so the animation's *start* value is per click.
 * With CSS that means writing custom properties and restarting the animation by
 * forcing a reflow, and restarting a CSS animation reliably is the kind of
 * thing that works until it does not. `Element.animate()` takes the keyframes
 * as data, returns a handle that can be cancelled, and drops the animation when
 * it finishes (`fill: "none"`), so nothing is left holding state.
 *
 * Every animated property is `transform` or `opacity`, so all of it composites
 * — no layout, no paint, nothing on the main thread per frame. The obvious
 * alternative (animating a `mask-image` radius over a copy of the grid) would
 * repaint a ~1200×750 layer every frame, on the page's LCP element, in response
 * to a click.
 *
 * ── Guards ──
 *
 *   • reduced motion — no listener at all. A burst is decorative motion by any
 *     reading. Note that the global `prefers-reduced-motion` reset in
 *     globals.css cannot help here: it collapses *CSS* animation and transition
 *     durations, and a WAAPI animation's timing is not a CSS property. The
 *     guard has to be in JS, and it is checked live on each event rather than
 *     captured at mount, so switching the preference mid-session takes effect.
 *   • interactive targets — a click on the CTA, a link or the status pill is a
 *     click on a control, and decorating it would make the control feel
 *     unpredictable.
 *   • secondary mouse buttons — the brief is the left button; a context-menu
 *     click should not fire it.
 *   • a 120ms floor between bursts, which absorbs the pointerdown/click pair
 *     and any double-tap.
 *
 * The layer is `pointer-events: none` and lives inside the hero panel's own
 * `overflow: hidden`, so the burst is bounded by the object it belongs to and
 * can never cover the headline, the subline or the CTA — those sit in a
 * `relative` sibling that paints above it.
 */

/** Grid pitch. Must match GRID_LINES in `ui/grid-backplate.tsx`. */
const CELL = 64;

/** Minimum gap between bursts, ms. Absorbs pointerdown/click and double-taps. */
const REARM_MS = 120;

/**
 * The four traces, as `[rotation°, cells travelled, delay ms, duration ms]`.
 *
 * The `ox`/`oy` corrections put each rotated segment exactly on the 1px row or
 * column the grid line occupies. A trace is drawn pointing along +x with
 * `transform-origin: 0 0`, so rotating it by 90° or 180° moves its 1px thickness
 * to the far side of the origin and leaves it one pixel off the line it is
 * supposed to be running along. At rest that is invisible; against a static
 * hairline it is a doubled line.
 */
const TRACES = [
  { deg: 0, cells: 3, delay: 0, duration: 780, ox: 0, oy: 0 }, // right
  { deg: 90, cells: 2.5, delay: 40, duration: 720, ox: 1, oy: 0 }, // down
  { deg: 180, cells: 2, delay: 20, duration: 680, ox: 0, oy: 1 }, // left
  { deg: 270, cells: 1.5, delay: 75, duration: 620, ox: 0, oy: 0 }, // up
] as const;

const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

export function HeroSignalBurst() {
  const layer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = layer.current;
    if (!host) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

    // The pool. Built here rather than in JSX so the markup this component
    // contributes to the server-rendered hero is a single empty <div> — the
    // decoration does not exist until something can drive it.
    const traces = TRACES.map(() => {
      const el = document.createElement("span");
      el.className = "hero-burst__trace";
      host.appendChild(el);
      return el;
    });

    const core = document.createElement("span");
    core.className = "hero-burst__core";
    host.appendChild(core);

    const ring = document.createElement("span");
    ring.className = "hero-burst__ring";
    host.appendChild(ring);

    const pool = [...traces, core, ring];
    let last = 0;

    function burst(px: number, py: number) {
      // Snap to the nearest grid intersection. This is the line between "the
      // system responded at a lattice point" and "a sparkle appeared where I
      // clicked", and it costs one rounding per axis.
      const x = Math.round(px / CELL) * CELL;
      const y = Math.round(py / CELL) * CELL;

      for (const el of pool) el.getAnimations().forEach((a) => a.cancel());

      traces.forEach((el, i) => {
        const t = TRACES[i];
        const from = `translate3d(${x + t.ox}px, ${y + t.oy}px, 0) rotate(${t.deg}deg)`;
        el.animate(
          [
            { transform: `${from} translate3d(0px, 0, 0)`, opacity: 0, offset: 0 },
            { opacity: 1, offset: 0.14 },
            {
              transform: `${from} translate3d(${t.cells * CELL}px, 0, 0)`,
              opacity: 0,
              offset: 1,
            },
          ],
          { duration: t.duration, delay: t.delay, easing: EASE, fill: "none" },
        );
      });

      // 3px is half the core's 6px box: the mark centres on the intersection
      // rather than hanging off its lower right.
      const at = `translate3d(${x - 3}px, ${y - 3}px, 0)`;
      core.animate(
        [
          { transform: `${at} scale(0.4)`, opacity: 0 },
          { transform: `${at} scale(1)`, opacity: 0.95, offset: 0.22 },
          { transform: `${at} scale(0.9)`, opacity: 0 },
        ],
        { duration: 620, easing: EASE, fill: "none" },
      );

      const ringAt = `translate3d(${x - 10}px, ${y - 10}px, 0)`;
      ring.animate(
        [
          { transform: `${ringAt} scale(0.35)`, opacity: 0 },
          { opacity: 0.75, offset: 0.18 },
          { transform: `${ringAt} scale(2.4)`, opacity: 0 },
        ],
        { duration: 880, easing: EASE, fill: "none" },
      );
    }

    function onPointerDown(e: PointerEvent) {
      if (reduce.matches) return;
      // Left button only. Touch and pen report button 0 too, so this does not
      // exclude them.
      if (e.button !== 0) return;

      const target = e.target as HTMLElement | null;
      if (target?.closest("a, button, input, textarea, select, [role='button']")) return;

      const now = e.timeStamp;
      if (now - last < REARM_MS) return;
      last = now;

      // Read against the layer's own box, which is `absolute inset-0` on the
      // same element the grid is — so this coordinate space and the grid's are
      // the same one, and the snap lands on a line that is actually drawn.
      const rect = host!.getBoundingClientRect();
      burst(e.clientX - rect.left, e.clientY - rect.top);
    }

    // The listener goes on the parent panel, not on this layer: the layer is
    // `pointer-events: none` and could not receive the event, and the effect
    // should answer a click anywhere on the panel.
    const panel = host.parentElement;
    panel?.addEventListener("pointerdown", onPointerDown, { passive: true });

    return () => {
      panel?.removeEventListener("pointerdown", onPointerDown);
      for (const el of pool) {
        el.getAnimations().forEach((a) => a.cancel());
        el.remove();
      }
    };
  }, []);

  return <div ref={layer} aria-hidden="true" className="hero-burst" />;
}
