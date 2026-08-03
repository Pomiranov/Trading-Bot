"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AssistantOrb } from "./assistant-orb";
import { AssistantPanel } from "./assistant-panel";

/**
 * Regions the orb must never sit on top of, on a screen narrow enough for it to
 * be over content at all.
 *
 * ── Why this list exists ──
 *
 * On a phone the page is full-bleed, so there is no gutter for a fixed launcher
 * to live in and *no* corner avoids content. Measured with a 44-position scroll
 * sweep at 320 / 360 / 390 / 430 under real touch emulation: docking left put the
 * orb on the "Получить доступ" CTA (720px²), two footer link columns (1031px² and
 * 588px²) and the locale switch; docking right removed all of those but still
 * clipped a FAQ trigger at every width, the access CTA at ≤360px, and a terminal
 * tab at 430px.
 *
 * Owner brief is explicit — "не перекрывать CTA, footer, FAQ и формы" — so the
 * residual overlaps are not something to accept quietly. The orb steps aside
 * instead.
 *
 * ── What it costs, stated plainly ──
 *
 * These five regions are most of the page below the hero, so on a phone the orb is
 * effectively present for the exploratory top of the page and absent for the
 * conversion path. That is the intended trade: an entry point to a feature that is
 * *not released yet* has no business covering the button that is.
 *
 * Nothing is lost that a reader needs — the assistant does not exist yet, and when
 * it does the honest fix is bottom padding on the page rather than a launcher that
 * hides. Revisit this list then.
 */
const DEFAULT_CLEAR_OF = ["#dashboard", "#pricing", "#faq", "#access", "footer"];

export interface AssistantLauncherProps {
  /**
   * What the orb does when pressed.
   *
   *   `placeholder` — opens `AssistantPanel`, which states that the assistant is
   *                   not available yet. The only supported value today.
   *   `live`        — hands off to `onOpen` and renders no panel of its own.
   *
   * This is the switch, and it is deliberately a prop rather than an environment
   * check: when the assistant is connected, the page decides per deployment
   * whether it is on, and a build-time flag cannot be flipped by a feature
   * gate or an A/B split.
   */
  mode?: "placeholder" | "live";
  /**
   * Called on every press, before anything else. In `placeholder` mode this is
   * the analytics hook; in `live` mode it is the whole implementation — mount the
   * thread view from here.
   */
  onOpen?: () => void;
  /**
   * Selectors the orb yields to on a narrow screen. Defaults to
   * `DEFAULT_CLEAR_OF` — read the note above it for the measurements behind that
   * list. Pass `[]` to pin the orb in place everywhere.
   */
  clearOf?: string[];
}

/**
 * The fixed entry point for the Quant assistant.
 *
 * ── What this replaced ──
 *
 * Nothing, and that is worth recording. The round button with an "N" in the
 * bottom-left corner of the dev site is Next.js's own dev-tools indicator —
 * verified by `aria-label="Open Next.js Dev Tools"` on a 32px button inside the
 * `nextjs-portal` shadow root — and it does not exist in a production build. It
 * was mistaken for site furniture, so this is a first build rather than a
 * redesign, and `devIndicators.position` in `next.config.ts` was moved to the
 * opposite corner so the two can no longer be confused.
 *
 * ── Where the state lives ──
 *
 * Here, and only here. `assistant-orb.tsx` is the sphere and takes no state;
 * `assistant-panel.tsx` is the placeholder copy and takes no state. This file
 * owns open/closed, the two dismissals, and focus restoration — which is the
 * whole of the interaction contract, and is what a real assistant would plug into
 * unchanged.
 *
 * ── Dismissal ──
 *
 * Escape, and a pointer press outside the dock. Both listeners are attached only
 * while the panel is open and removed on close, so nothing is left listening on a
 * page where the panel has never been used — the common case.
 *
 * `pointerdown` rather than `click` for the outside press: a `click` fires after
 * the pointer is released, so a reader who presses outside and drags back in
 * would dismiss a panel they visibly changed their mind about.
 *
 * ── Position ──
 *
 * Bottom-left, fixed, `--z-launcher` (60) — above the page, below the mobile nav
 * overlay at 90 so it cannot float over an open menu. The dock itself is
 * `pointer-events: none` and only the orb re-enables them, so the fixed corner
 * can never swallow a click meant for the content behind it. See `.assistant-dock`
 * in globals.css.
 */
export function AssistantLauncher({
  mode = "placeholder",
  onOpen,
  clearOf = DEFAULT_CLEAR_OF,
}: AssistantLauncherProps) {
  const t = useTranslations("assistant");
  const [open, setOpen] = useState(false);
  const [stood, setStood] = useState(false);
  const panelId = useId();
  const dockRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const orbRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);

  const toggle = useCallback(() => {
    onOpen?.();
    // In `live` mode this component renders no panel, so there is no local state
    // to flip — `onOpen` is the entire behaviour and the caller owns what happens
    // next. Toggling anyway would leave `aria-expanded="true"` pointing at an
    // empty region.
    if (mode === "placeholder") setOpen((v) => !v);
  }, [mode, onOpen]);

  // Focus follows the disclosure: into the panel on open, back to the orb on
  // close. Guarded on `open` having actually changed rather than running on every
  // render, so this cannot steal focus while the reader is elsewhere on the page.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  /**
   * Stand the orb down while a protected region is on screen.
   *
   * ── Gating ──
   *
   * `(max-width: 767px)` is deliberately a *width* query and not `pointer: coarse`.
   * The problem is geometric — a full-bleed column with no gutter — so the
   * condition has to be the viewport, not the input device. A desktop browser at a
   * narrow window has the same layout and needs the same behaviour; a touch laptop
   * at 1440px does not. It matches the breakpoint the dock's own CSS switches
   * corners at, so the two cannot disagree.
   *
   * ── Why IntersectionObserver and not a scroll handler ──
   *
   * A scroll listener would run on the main thread on every frame of a Lenis-driven
   * smooth scroll, for a boolean that changes maybe six times per page. The
   * observer fires only on crossings and costs nothing in between.
   *
   * The whole effect is re-run when the query flips, and it tears down its own
   * observer and listener on every path — including the early return, where there
   * is nothing to tear down but `stood` must still be cleared so that a reader who
   * resizes from a phone width to a desktop one does not keep a hidden orb.
   */
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");

    let io: IntersectionObserver | undefined;

    const attach = () => {
      io?.disconnect();
      io = undefined;

      if (!mq.matches || clearOf.length === 0) {
        setStood(false);
        return;
      }

      const targets = clearOf
        .flatMap((sel) => Array.from(document.querySelectorAll(sel)))
        .filter((el): el is Element => Boolean(el));

      if (targets.length === 0) {
        setStood(false);
        return;
      }

      // One observer, many targets, and the state is "is *any* of them showing".
      // `entry.isIntersecting` per-target is not enough on its own: two protected
      // regions are adjacent, so the leaving one fires false in the same callback
      // the arriving one fires true, and reading either in isolation flickers.
      const showing = new Set<Element>();
      io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            if (e.isIntersecting) showing.add(e.target);
            else showing.delete(e.target);
          }
          setStood(showing.size > 0);
        },
        // A little margin, so the orb is already gone by the time the region's
        // first row is readable rather than dissolving on top of it.
        { rootMargin: "0px 0px -12% 0px" },
      );
      targets.forEach((el) => io!.observe(el));
    };

    attach();
    mq.addEventListener("change", attach);
    return () => {
      mq.removeEventListener("change", attach);
      io?.disconnect();
    };
  }, [clearOf]);

  // A stood-down orb must not keep an open panel floating over the region it just
  // yielded to.
  useEffect(() => {
    if (stood) setOpen(false);
  }, [stood]);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      close();
      // Return focus explicitly. The panel is about to be `hidden`, and focus on
      // a hidden element falls to <body>, which would drop the reader at the top
      // of the page.
      orbRef.current?.querySelector("button")?.focus();
    };

    const onPointerDown = (e: PointerEvent) => {
      if (dockRef.current?.contains(e.target as Node)) return;
      close();
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open, close]);

  return (
    <div ref={dockRef} className="assistant-dock" data-open={open} data-stood={stood}>
      {mode === "placeholder" ? (
        <AssistantPanel
          id={panelId}
          ref={panelRef}
          open={open}
          title={t("title")}
          body={t("body")}
          closeLabel={t("close")}
          onClose={() => {
            close();
            orbRef.current?.querySelector("button")?.focus();
          }}
        />
      ) : null}

      <div ref={orbRef} className="assistant-dock__row">
        <AssistantOrb open={open} controls={panelId} label={t("open")} onClick={toggle} />
        {/*
          The visible name, revealed on hover and on keyboard focus.

          The orb carries no glyph — see the note in `assistant-orb.tsx` — so
          without this the only thing identifying it is `aria-label`, which a
          sighted mouse user never hears. `aria-hidden` because that same label is
          already the button's accessible name and reading it twice is noise.

          `pointer-events: none` in the CSS: the chip sits in the fixed dock beside
          the button, and a label is not a target.
        */}
        <span aria-hidden="true" className="assistant-dock__hint">
          {t("hint")}
        </span>
      </div>
    </div>
  );
}
