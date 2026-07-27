import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Wraps a horizontal scroller and makes the fact that it scrolls *visible*.
 *
 * The defect: the strategy register is `min-w-[680px]` inside an
 * `overflow-x-auto` container. Measured at 390px — container 358, content 702,
 * so **344px of the table is reachable only by a horizontal gesture** and there
 * is nothing on screen to suggest it exists. The implementation is correct
 * (the scroller is axis-scoped and does not break the page); it is simply
 * undiscoverable.
 *
 * Two cues, both of them cheap:
 *   1. a gradient fade on the right edge, which is the standard "there is more
 *      this way" signal and also stops the content from being cut mid-glyph
 *   2. a short mono hint below, shown only where the scroller can actually
 *      appear
 *
 * ── `data-lenis-prevent-horizontal`, not `data-lenis-prevent` ──
 *
 * This is load-bearing and must be passed down to the scrolling element by the
 * caller. The bare attribute opts the element out of Lenis on *both* axes, so
 * vertical wheel input over the table scrolls the page natively while Lenis'
 * internal position stays put — and the next wheel event animates from a stale
 * origin, lurching the page backward. That is the site's worst historical bug.
 * The axis-scoped form releases horizontal gestures only.
 */
export function ScrollAffordance({
  hint,
  className,
  children,
}: {
  /** Short instruction, e.g. "Прокрутите таблицу вбок". */
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="relative">
        {children}
        {/* Edge fade. Sits above the scroller but must never eat its events. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-px right-px w-12 rounded-r-[var(--radius-lg)] bg-gradient-to-l from-[color:var(--color-surface)] to-transparent md:hidden"
        />
      </div>
      {hint ? (
        <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase md:hidden">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
