"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { getLenis } from "@/components/motion/scroll-driver";
import { buttonVariants } from "@/components/ui/button";
import { Link } from "@/lib/i18n/navigation";
import type { Locale } from "@/lib/i18n/routing";
import { track } from "@/lib/analytics/events";
import { cn } from "@/lib/utils";

interface NavLink {
  key: string;
  label: string;
  href: string;
}

export function MobileNav({
  links,
  navLabel,
  ctaLabel,
  localeSwitchLabel,
  localeSwitchLocale,
  localeSwitchAriaLabel,
  openLabel,
  closeLabel,
}: {
  links: NavLink[];
  navLabel: string;
  ctaLabel: string;
  localeSwitchLabel: string;
  localeSwitchLocale: Locale;
  localeSwitchAriaLabel: string;
  openLabel: string;
  closeLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  const toggleRef = useRef<HTMLButtonElement>(null);

  /**
   * Release the scroll lock *synchronously*, then close.
   *
   * The ordering here is load-bearing and cost an outright broken link to find.
   * A tap on an in-panel anchor dispatches: React's `onClick` (this function) →
   * the document-level interceptor in motion/lenis-provider.tsx → React commit →
   * effect cleanup. That interceptor calls `lenis.scrollTo(el, …)` *without*
   * `force`, and Lenis drops a non-forced `scrollTo` while it is stopped. So if
   * the lock were released only in the effect cleanup — one step too late — every
   * link in this menu would close the panel and navigate nowhere.
   *
   * Releasing before `setOpen(false)` means Lenis is already running by the time
   * the interceptor sees the click. The effect cleanup repeats both operations;
   * `start()` and restoring `overflow` are both idempotent, so that is harmless
   * and keeps the unmount path correct on its own.
   */
  function close() {
    getLenis()?.start();
    document.documentElement.style.overflow = "";
    setOpen(false);
  }

  /**
   * The three things an open overlay owes the reader, none of which were here.
   *
   * Measured on the live page before this: with the panel open, Escape did
   * nothing (`aria-expanded` stayed `true`), the document scrolled freely
   * underneath — the panel is `position: fixed`, so it stayed put while the page
   * ran past behind it — and at 390px the nav labels ended up sitting on top of
   * the audience cards' body copy. A menu that cannot be dismissed by the two
   * gestures every reader already knows is a trap, and one that lets the page
   * move behind it reads as a rendering fault rather than as a layer.
   *
   *   1. **Escape closes.** Keyed off `open` so no listener exists while closed.
   *   2. **Scroll is locked, on both paths.** Lenis owns scroll here, so the
   *      lock is `lenis.stop()` — reaching around it with `overflow: hidden`
   *      alone would leave its RAF loop animating a position the document no
   *      longer honours, which is the class of desync documented at length in
   *      scroll-driver.ts. But under reduced motion Lenis is never instantiated
   *      at all, so the overflow lock is the only thing holding that path, and it
   *      has to go on `documentElement`: measured with a real wheel event, the
   *      first version set it on `body` and the page scrolled 900px with the
   *      panel open, because the scrolling box on this document is `<html>`.
   *      Both are applied, so neither path depends on the other.
   *   3. **Focus comes back.** Dismissing returns it to the toggle that opened
   *      the panel, rather than dropping it at the top of the document.
   *
   * The cleanup runs on close *and* on unmount, so a locale switch mid-open
   * cannot leave the page unscrollable.
   */
  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
        toggleRef.current?.focus();
      }
    }

    /**
     * Crossing `lg` while open hides the panel and toggle (`lg:hidden`) but
     * not this effect: the scrim stayed over the page and scroll stayed
     * locked, with nothing visible left to dismiss either. Close for real
     * when the layout switches to the desktop nav.
     */
    const desktop = window.matchMedia("(min-width: 1024px)");
    function onDesktopChange(event: MediaQueryListEvent) {
      if (event.matches) close();
    }

    const lenis = getLenis();
    const root = document.documentElement;
    const previousOverflow = root.style.overflow;

    lenis?.stop();
    root.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    desktop.addEventListener("change", onDesktopChange);

    return () => {
      desktop.removeEventListener("change", onDesktopChange);
      window.removeEventListener("keydown", onKeyDown);
      root.style.overflow = previousOverflow;
      lenis?.start();
    };
  }, [open]);

  return (
    <>
      {/* Hamburger toggle */}
      <button
        ref={toggleRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        aria-controls="mobile-nav-panel"
        aria-label={open ? closeLabel : openLabel}
        className="relative flex size-11 flex-col items-center justify-center gap-[5.5px] rounded-[var(--radius-md)] border transition-colors duration-[var(--duration-base)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] lg:hidden"
        style={{
          background: open ? "var(--color-highlight-bg)" : "var(--color-fill-subtle)",
          borderColor: open ? "var(--color-highlight-border)" : "var(--color-border-strong)",
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-px w-[14px] rounded-full transition-all duration-300 origin-center"
            style={{
              background: open ? "var(--color-accent)" : "var(--color-text-secondary)",
              opacity: i === 1 && open ? 0 : 1,
              transform:
                open
                  ? i === 0
                    ? "translateY(5.5px) rotate(45deg)"
                    : i === 2
                    ? "translateY(-5.5px) rotate(-45deg)"
                    : "none"
                  : "none",
            }}
          />
        ))}
      </button>

      <AnimatePresence>
        {open && (
          <>
            {/*
              Tap-outside backdrop, and now also a scrim.

              It used to be fully transparent — it existed only to catch the
              dismiss tap. That left the panel as the sole thing separating its
              own 11px mono labels from whatever card copy happened to be behind
              them, and the panel is translucent glass by design. A 55% scrim
              puts the page a clear step back instead, which is also what makes
              the blur read as "this layer is in front" rather than as a
              rendering artefact.
            */}
            <motion.div
              key="backdrop"
              className="fixed inset-0 lg:hidden"
              style={{
                zIndex: "calc(var(--z-nav) - 2)",
                background: "var(--color-scrim)",
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={() => {
                close();
                toggleRef.current?.focus();
              }}
              aria-hidden="true"
            />

            {/* Dropdown panel */}
            <motion.nav
              key="panel"
              id="mobile-nav-panel"
              aria-label={navLabel}
              /**
               * This stays a disclosure, not a `role=dialog`, so there is no
               * focus trap — instead, when Tab carries focus out of the panel
               * into the scrimmed page, close it. The toggle is exempt so
               * Shift+Tab back to it does not slam the panel shut, and a null
               * `relatedTarget` (window blur, tap on non-focusable content) is
               * ignored — the scrim's own click handler covers that case.
               */
              onBlur={(event) => {
                const next = event.relatedTarget as Node | null;
                if (
                  next &&
                  !event.currentTarget.contains(next) &&
                  !toggleRef.current?.contains(next)
                ) {
                  close();
                }
              }}
              className="fixed left-4 right-4 top-[var(--nav-panel-top)] lg:hidden overflow-x-hidden overflow-y-auto rounded-[var(--radius-xl)]"
              style={{
                zIndex: "calc(var(--z-nav) - 1)",
                background: "var(--color-glass-surface-strong)",
                backdropFilter: "blur(32px)",
                WebkitBackdropFilter: "blur(32px)",
                border: "1px solid var(--color-glass-border)",
                boxShadow: "var(--shadow-nav-panel)",
                /**
                 * Document scroll is locked while open, so anything past the
                 * viewport edge is unreachable — on a landscape phone (667×375)
                 * that was the whole bottom row. Cap the panel to the space
                 * below its top offset and let it scroll internally instead
                 * (`overflow-y-auto` above, was `overflow-hidden`).
                 */
                maxHeight: "calc(100dvh - var(--nav-panel-top) - 16px)",
              }}
              initial={reduce ? false : { opacity: 0, y: -8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              {/* Nav links */}
              <div className="flex flex-col p-3 gap-0.5">
                {links.map(({ key, label, href }, i) => (
                  <motion.a
                    key={key}
                    href={href}
                    onClick={() => {
                      track({ name: "journey_step", props: { section: key } });
                      close();
                    }}
                    className="flex min-h-11 items-center rounded-[var(--radius-md)] px-3 py-3 font-mono text-[length:var(--text-caption)] tracking-[0.1em] text-[color:var(--color-text-secondary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:bg-[color:var(--color-highlight-bg)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                    initial={reduce ? false : { opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: 0.2,
                      delay: 0.05 + i * 0.04,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  >
                    {label}
                  </motion.a>
                ))}
              </div>

              {/* Divider */}
              <div
                className="mx-3"
                style={{ height: "1px", background: "var(--color-border)" }}
              />

              {/* Bottom row: locale switch + CTA */}
              <div className="flex items-center justify-between gap-3 p-3">
                {/*
                  next-intl's `Link` with `locale=`, matching the header and
                  footer switches — the bare `<a href="/{code}">` it replaces
                  forced a full document reload on the one surface where every
                  other locale switch navigated client-side. `aria-label`
                  states the action; a bare "EN" chip does not.
                  `min-h-11` + `inline-flex items-center`: at `py-2.5` this
                  measured ~36px, under the 44px touch floor.
                */}
                <Link
                  href="/"
                  locale={localeSwitchLocale}
                  onClick={close}
                  aria-label={localeSwitchAriaLabel}
                  className="inline-flex min-h-11 items-center rounded-[var(--radius-md)] border border-[color:var(--color-border-strong)] px-3 py-2.5 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                >
                  {localeSwitchLabel}
                </Link>
                {/*
                  ── Was the last hand-rolled button on the page ──

                  This anchor re-declared the `default` variant's look by hand —
                  white fill, mono uppercase, semibold, 0.1em — and therefore got
                  none of its behaviour: no depth, no resting or hover shadow, no
                  press, no hover state at all. On a phone, where this is the only
                  CTA in the navigation, the page's primary action was the one
                  control that did not respond to being touched.

                  `buttonVariants()` rather than `ButtonLink`, because this needs an
                  `onClick` that also closes the panel and `ButtonLink` deliberately
                  owns that handler for its analytics call. Same class string,
                  same system, one import.

                  `size="default"` (h-11) rather than the old `py-2.5`: that
                  computed to ~40px, under the 44px touch floor, on the one target
                  a phone visitor is most likely to aim for.
                */}
                <a
                  href="#access"
                  onClick={() => {
                    track({ name: "cta_clicked", props: { target: "sandbox_access", location: "mobile_nav" } });
                    close();
                  }}
                  className={cn(buttonVariants({ size: "default" }), "no-underline")}
                >
                  {ctaLabel}
                </a>
              </div>
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
