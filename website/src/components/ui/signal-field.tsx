"use client";

import { useEffect, useRef, type ReactNode } from "react";
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
 */
export function SignalField({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

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
      const node = ref.current;
      if (!node) return;
      // getBoundingClientRect is read here, inside a pointer handler, which is
      // not a scroll read — the constraint this codebase enforces is on scroll
      // position, and `left`/`top` are viewport-relative geometry the browser
      // has already computed for this frame's hit test.
      const rect = node.getBoundingClientRect();
      pending = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const n = ref.current;
        if (!n || !pending) return;
        n.style.setProperty("--signal-x", `${pending.x.toFixed(1)}px`);
        n.style.setProperty("--signal-y", `${pending.y.toFixed(1)}px`);
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

  return (
    <div ref={ref} className={cn("signal-field", className)}>
      {children}
    </div>
  );
}
