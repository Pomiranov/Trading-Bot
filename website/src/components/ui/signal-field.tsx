"use client";

import {
  createElement,
  useEffect,
  useRef,
  type ComponentPropsWithoutRef,
  type ElementType,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

/**
 * Makes the decorative geometry inside a panel light up where the pointer is.
 *
 * ── What it is for ──
 *
 * The hero and the closing CTA are both dark panels with a faint technical grid
 * behind them. Static, that grid is atmosphere. Under a pointer it becomes the
 * one interaction on the page that reads as *instrumentation responding* — the
 * lines nearest the cursor take on the cold signal colour and fade back as it
 * moves away, like a field being probed.
 *
 * ── How, and why this shape ──
 *
 * This component does one thing: it writes the pointer's position inside its own
 * box to three custom properties, and nothing else.
 *
 *     --signal-x, --signal-y   position, in px, relative to this element
 *     --signal-on              0 or 1 — whether the pointer is over it at all
 *
 * Every visual consequence is CSS, keyed off those variables (see
 * `.signal-field__grid` in globals.css and the `signal` prop on
 * `ui/grid-backplate.tsx`). That split is deliberate: the effect can then be
 * applied to any decoration inside the subtree without this file knowing what
 * that decoration is, and the whole thing costs one custom-property write per
 * frame with no React re-render — the state never enters React at all.
 *
 * The lit layer is a cyan-masked copy of geometry that is already there, so it
 * paints and composites but never lays out. `--signal-on` gates opacity, so
 * with no pointer, no JS, or a failed effect the value is unset, the layer is
 * fully transparent, and the panel is exactly what it was. There is no state in
 * which this can shift the layout by a pixel.
 *
 * ── Guards, and why the markup never branches on them ──
 *
 * Same rule as `hero/pointer-tilt.tsx` and `motion/reveal.tsx`: the element and
 * its classes are identical on the server and on every client, and the
 * preference only decides whether the *listener* is installed. Branching markup
 * on a media query read during render is what produced the "all 32 cards stuck
 * at opacity 0" bug.
 *
 *   • reduced motion — no listener. A glow that chases the cursor is decorative
 *     motion by any reading, and it is the first thing that should go.
 *   • coarse pointer — no listener. There is no hover on a touch screen, and the
 *     last touch position would stick as a bright patch after the finger lifted.
 *   • rAF coalescing — a 1000Hz pointer stream still writes at most once a frame.
 *
 * `pointerleave` clears `--signal-on` rather than the coordinates, so the glow
 * fades out *in place* instead of sliding back to the top-left corner on the way
 * out. That difference is the whole reason it reads as a light going out rather
 * than as an element being moved.
 *
 * ── `as`, and why the field is not always a <div> ──
 *
 * The two dark panels wrap their content, so a <div> is the right element for
 * them. The two paper bands do not: their field is the *section itself*, because
 * the grid now runs the full height of the band rather than sitting inside a
 * panel, and the pointer has to be tracked over that whole area.
 *
 * Rendering an extra wrapper <div> inside the <section> would not work — it would
 * be the padding box, so the grid could not reach the section's edges — and
 * wrapping the <section> in a <div> would put a non-landmark between <main> and
 * its sections. `as="section"` lets `ui/section.tsx` make the section element
 * itself the field, with every section attribute (id, aria-labelledby,
 * data-rhythm) spread straight through.
 */
export function SignalField<T extends ElementType = "div">({
  as,
  className,
  children,
  ...rest
}: { as?: T; className?: string; children: ReactNode } & Omit<
  ComponentPropsWithoutRef<T>,
  "as" | "className" | "children"
>) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) {
      return;
    }

    let frame = 0;
    let pending: { x: number; y: number } | null = null;

    function onPointerMove(e: PointerEvent) {
      // Only the client coordinates are captured per event; the geometry read
      // lives inside the rAF callback below. The handler used to call
      // getBoundingClientRect per raw event, which on a 1000Hz pointer is up
      // to ~16 forced geometry reads a frame on a full-width section — the
      // rAF was coalescing the *writes* while the *reads* ran unthrottled.
      // One read per painted frame is the actual budget.
      pending = { x: e.clientX, y: e.clientY };
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const n = ref.current;
        if (!n || !pending) return;
        const rect = n.getBoundingClientRect();
        n.style.setProperty("--signal-x", `${(pending.x - rect.left).toFixed(1)}px`);
        n.style.setProperty("--signal-y", `${(pending.y - rect.top).toFixed(1)}px`);
        n.style.setProperty("--signal-on", "1");
      });
    }

    function onLeave() {
      const node = ref.current;
      if (!node) return;
      // Position deliberately retained — see the note above.
      node.style.setProperty("--signal-on", "0");
    }

    el.addEventListener("pointermove", onPointerMove, { passive: true });
    el.addEventListener("pointerleave", onLeave);

    return () => {
      if (frame) cancelAnimationFrame(frame);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerleave", onLeave);
      onLeave();
    };
  }, []);

  // createElement, not JSX, for the polymorphic tag — the same escape hatch
  // `ui/mono-label.tsx` uses, and for the same reason: TS cannot verify an
  // arbitrary generic ElementType's props against JSX.IntrinsicElements.
  return createElement(
    as ?? "div",
    { ref, className: cn("signal-field", className), ...rest },
    children,
  );
}
