"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Gives the header its behaviour: present over the hero, then out of the way.
 *
 * ── Three states, not two ──
 *
 *   at rest   — transparent, no border, no blur. The hero gets a clean top edge;
 *               the first thing a visitor sees is the artwork, not a bar sitting
 *               on it.
 *   compact   — the glass pill, once the page has moved off the very top.
 *   retracted — translated up out of the viewport, faded, and slightly
 *               compressed, from the moment the pill would touch `#audience`.
 *
 * The boundary between the last two is a measured position on this page, not a
 * round number: see `retractGateFor` below, which is where the timing lives.
 *
 * The retracted state is the point of this component. The header used to hold
 * its compact state for the whole page, which meant a 62px pill parked over
 * every section a reader scrolled to — measured, it overlapped the `#audience`
 * H2, the `#foundation` eyebrow and the `#pricing` lead, and on the two paper
 * bands the black scrim behind it sat on white as a grey smear. A sticky nav is
 * useful for navigating and merely in the way while reading, so it now leaves
 * while the reader reads and comes back the moment they ask for it.
 *
 * ── What brings it back ──
 *
 *   • scrolling up by more than SENTINEL_GAP — the intent to leave the current
 *     block. This is the only recovery on a touch device, which is why that
 *     constant is sized against a phone viewport rather than a laptop one.
 *   • returning to the top of the page — back to the at-rest state
 *   • keyboard focus reaching anything inside it, via `:focus-within`, so Tab
 *     never lands on an invisible control
 *   • hovering the top edge of the viewport, via the sensor strip below.
 *     Pointer devices only, deliberately: a full-width 64px band across the top
 *     of a phone screen would swallow taps aimed at the content under it.
 *
 * ── Why direction is read from IntersectionObserver and not from scrollY ──
 *
 * The rule this file already obeyed, and the one most worth keeping: nothing on
 * this page may read scroll position except `motion/scroll-driver.ts`. A second
 * reader on the value Lenis animates is precisely the coupling that produced the
 * backward-scroll bug documented in that module, and a `scroll` handler here —
 * the obvious way to write a hide-on-scroll-down header — would reintroduce it
 * exactly.
 *
 * So direction is derived from a *stack of sentinels* instead. A short column of
 * zero-height markers is laid down the page; each one reports when it crosses
 * the viewport's top edge, and the sign of the change in which markers are
 * "above" tells us whether the reader moved down or up. That is push-based, it
 * costs nothing per frame, and it never asks the document where it is.
 *
 * `IntersectionObserverEntry.boundingClientRect` is read only inside the
 * observer callback, which is a value the browser has already computed and
 * handed us — not a layout query we forced, and not the scroll offset.
 *
 * ── The height still must not change ──
 *
 * `NAV_OFFSET` (104) and the `scroll-margin-top` in globals.css are one number
 * shared by the anchor interceptor and the no-JS path, so the pill's box is
 * identical in all three states. Retracting uses `transform` and `opacity`
 * only — both compositor-only, both outside layout — so the CLS contribution
 * stays zero and every deep link lands in the same place in every state.
 */

/**
 * Vertical spacing between direction sentinels.
 *
 * 420px, down from 600. The gap is the *granularity of recovery*: a retracted
 * header comes back when the reader crosses one going up, so 600px meant a
 * reader had to scroll up two thirds of a laptop screen — and most of a phone
 * screen — before the navigation returned. On touch that is the only recovery
 * there is, because the hover sensor below is inert without a pointer.
 *
 * 420px is still far more than a reader moves while re-reading a line, so it
 * cannot flicker from ordinary reading, and it is about half a phone viewport,
 * which is a deliberate gesture. It has to stay comfortably under one viewport
 * or a single upward flick could fail to cross any sentinel at all.
 *
 * The sentinels only have to be dense enough that a crossing reliably means
 * "the reader has moved", never dense enough to track position.
 */
const SENTINEL_GAP = 420;

/**
 * Sentinel count above which the header is allowed to retract at all.
 *
 * 0 — and the number is only meaningful together with where the track *starts*,
 * which is now the `#audience` boundary rather than a fixed offset. See
 * `retractGateFor` below. With the first sentinel sitting exactly on that
 * boundary, "more than zero sentinels are above the viewport top" reads as "the
 * reader has entered the content", which is the condition the header should
 * retract on.
 */
const RETRACT_AFTER = 0;

/**
 * Fallback gate for the case where `#audience` cannot be found, in document px.
 * Only reachable if the page composition changes underneath this component;
 * roughly one viewport, so the header still never retracts on the hero.
 */
const GATE_FALLBACK = 900;

/**
 * Never gate above this, in document px. Guards the degenerate case — a very
 * short hero on a very tall viewport — where the boundary could land close
 * enough to the top that the header retracts as soon as the reader nudges the
 * page.
 */
const GATE_MIN = 320;

/**
 * Distance from the top of the document to an element, without reading scroll
 * position.
 *
 * `getBoundingClientRect().top + scrollY` is the obvious form and it is exactly
 * the thing this file may not do — see the note at the top on why nothing here
 * may read the value Lenis animates. Walking `offsetTop` up the `offsetParent`
 * chain is a pure layout read: it is the same category as the `scrollHeight`
 * read in the measure effect below, it does not change while scrolling, and it
 * is taken twice per resize.
 */
function documentTop(el: HTMLElement): number {
  let y = 0;
  let node: HTMLElement | null = el;
  while (node) {
    y += node.offsetTop;
    node = node.offsetParent as HTMLElement | null;
  }
  return y;
}

/**
 * Where the header is allowed to start retracting.
 *
 * ── The defect this replaces ──
 *
 * The track used to start at a flat 600px, which is not a position on this
 * page — it is a number that happened to be under one viewport. Measured at
 * 757×798 the hero is 857px tall and `#audience` begins at 857, so the header
 * was leaving at 600: 171px early, with the hero still filling the screen and
 * the reader given no reason for the navigation to go. At 1440×900 the hero is
 * taller and the error is larger.
 *
 * The owner's description of the intended behaviour is precise — the header
 * should retract "при соприкосновении с блоком Аудитория", when it *touches*
 * the audience block — and that moment is exactly computable: the section's top
 * edge reaches the pill's bottom edge when the page has scrolled
 * `audienceTop − navHeight`. Before that instant the header is over the hero,
 * which is its designed state; after it, the header would be over content.
 *
 * `--nav-height` is read rather than hard-coded so this stays correct with the
 * one number that already governs the pill's box (see the header-geometry block
 * in globals.css).
 */
function retractGateFor(): number {
  const audience = document.getElementById("audience");
  if (!audience) return GATE_FALLBACK;

  const navHeight =
    Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--nav-height"),
    ) || 86;

  return Math.max(GATE_MIN, documentTop(audience) - navHeight);
}

/**
 * Keeps the last sentinel this far above the end of the scrollable range.
 *
 * ── The bug this exists to prevent ──
 *
 * The first version laid down a fixed 40 sentinels at 900px intervals, putting
 * the last one at y=36 000px. Absolutely-positioned elements still contribute to
 * their containing block's scroll height, so the document grew from ~14 000px to
 * exactly 36 001px — 22 000px of empty scroll past the footer, measured. A
 * zero-height container does not help: it is the children's offsets that count.
 *
 * So the count is derived from the document instead, and every sentinel is placed
 * strictly inside the range the reader can already reach. A sentinel that cannot
 * extend the document cannot be the reason the document is longer.
 */
const SENTINEL_TAIL_MARGIN = 200;

export function HeaderShell({ children }: { children: ReactNode }) {
  const [compact, setCompact] = useState(false);
  const [retracted, setRetracted] = useState(false);
  /**
   * Where the direction track starts and how many markers it holds.
   *
   * `count: 0` on the server and on first paint. The sentinels are aria-hidden
   * decoration whose only job is to inform an enhancement, so rendering none of
   * them until the document has been measured costs nothing: the header simply
   * stays in its default non-retracted state until then.
   */
  const [track, setTrack] = useState({ gate: GATE_FALLBACK, count: 0 });
  const topSentinel = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = topSentinel.current;
    if (!el) return;

    const io = new IntersectionObserver(
      // The sentinel sits at y=100px in the document. While it is on screen the
      // page has not scrolled past 100px, so the header stays transparent; once
      // it leaves through the top, the header goes compact.
      ([entry]) => {
        setCompact(!entry.isIntersecting);
        // Returning to the very top always restores the header, whatever the
        // direction bookkeeping below currently believes.
        if (entry.isIntersecting) setRetracted(false);
      },
      { threshold: 0 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  /**
   * Size the sentinel track to the document.
   *
   * `scrollHeight` and `innerHeight` are layout reads, not scroll-position reads
   * — the constraint this file obeys is that nothing may read or write *where the
   * page is scrolled to*, because that is the value Lenis animates. How tall the
   * document is is not that value, it does not change while scrolling, and it is
   * read here exactly twice per resize.
   *
   * Re-measured on resize because the document's height changes with viewport
   * width: at 390px this page is roughly twice as tall as at 1440px, and a track
   * sized for the wide case would leave the bottom half of the narrow page with
   * no sentinels in it.
   *
   * The gate is re-measured with it, and for the same reason with more force:
   * it is derived from the hero's height, and the hero is `min-h-dvh` above
   * `md` and content-sized below it. A gate measured at one width is simply the
   * wrong number at another.
   */
  useEffect(() => {
    let timer: number | undefined;

    function measure() {
      const gate = retractGateFor();
      const reachable =
        document.documentElement.scrollHeight -
        window.innerHeight -
        SENTINEL_TAIL_MARGIN -
        gate;
      const count = Math.max(0, Math.floor(reachable / SENTINEL_GAP) + 1);
      // Bail on an unchanged measurement: this setter re-subscribes the
      // direction observer below, and a resize that does not move the gate
      // should not cost a teardown.
      setTrack((prev) => (prev.gate === gate && prev.count === count ? prev : { gate, count }));
    }

    function onResize() {
      window.clearTimeout(timer);
      timer = window.setTimeout(measure, 150);
    }

    measure();
    // Fonts and images settle after `load` and can change the height materially.
    if (document.readyState !== "complete") window.addEventListener("load", measure);
    window.addEventListener("resize", onResize);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("load", measure);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  useEffect(() => {
    // `trackEl`, not `track`: the state of the same name is read in the
    // dependency array below, and shadowing it here reads as a bug.
    const trackEl = trackRef.current;
    if (!trackEl) return;

    const marks = Array.from(trackEl.children) as HTMLElement[];
    if (marks.length === 0) return;

    // Reset the bookkeeping attribute on every re-subscribe. React reuses these
    // DOM nodes across renders (they are keyed by index), so a track rebuilt at
    // a new gate after a resize would otherwise inherit the previous layout's
    // `data-above` flags and mis-count the first callback by however many
    // markers changed side.
    for (const mark of marks) mark.setAttribute("data-above", "false");

    /**
     * How many sentinels are currently above the viewport's top edge. The count
     * is a monotonic proxy for depth — it rises going down and falls going up —
     * and comparing it with the previous count gives direction without ever
     * reading `scrollY`.
     */
    let above = 0;
    let settled = false;

    const io = new IntersectionObserver(
      (entries) => {
        let next = above;
        for (const entry of entries) {
          // `boundingClientRect` here is the value the observer already
          // computed. Reading it does not force layout and does not query
          // scroll position.
          const isAbove = entry.boundingClientRect.top < 0;
          const wasCounted = entry.target.getAttribute("data-above") === "true";
          if (isAbove && !wasCounted) {
            next += 1;
            entry.target.setAttribute("data-above", "true");
          } else if (!isAbove && wasCounted) {
            next -= 1;
            entry.target.setAttribute("data-above", "false");
          }
        }

        // The first callback fires on observe and reports the initial state for
        // every sentinel at once. That is not a scroll, so it must not be read
        // as a direction — otherwise a deep link would retract the header before
        // the reader had moved.
        if (!settled) {
          settled = true;
          above = next;
          return;
        }

        if (next > above) {
          // Downward, and at or past the `#audience` boundary — marker 0 sits
          // exactly on it. Retract.
          if (next > RETRACT_AFTER) setRetracted(true);
        } else if (next < above) {
          // Upward. The reader wants out of this block — bring the nav back.
          setRetracted(false);
        }
        above = next;
      },
      { threshold: 0 },
    );

    for (const mark of marks) io.observe(mark);
    return () => io.disconnect();
    // Re-subscribes when the track is rebuilt at a new gate or length after a
    // resize. The measure effect above suppresses no-op updates, so this does
    // not tear down on every resize event.
  }, [track.gate, track.count]);

  return (
    <>
      {/*
        Observer target for the compact state, parked at the scroll depth where
        the header should change — *not* at y=0 with a negative rootMargin. That
        was the first attempt and it is inverted: a -100px top margin also
        excludes the top 100px of the viewport, so a sentinel at y=0 reads as
        "not intersecting" while the page is still at the top, and the header
        rendered compact over the hero — the exact thing this state exists to
        avoid.

        Absolute and 1px, so it takes no space and cannot affect layout.
      */}
      <div
        ref={topSentinel}
        aria-hidden="true"
        className="pointer-events-none absolute top-[100px] left-0 h-px w-px"
      />

      {/*
        The direction track: a column of 1px markers down the document.

        It starts *at the retract gate* — the `#audience` boundary — rather than
        one gap below the top of the page, which is the whole of the timing fix.
        Marker 0 sits exactly on the boundary, so crossing it downward is both
        "the reader moved down" and "the reader has left the hero", and
        RETRACT_AFTER can stay 0 while meaning something real about the page.

        Every marker sits at a `top` inside the range the reader can already
        scroll to — see SENTINEL_TAIL_MARGIN for the 22 000px of phantom page the
        naive version of this produced. Both the gate and the count are
        measured, not fixed, so the track starts and ends where the document
        does at the current viewport width.
      */}
      <div
        ref={trackRef}
        aria-hidden="true"
        className="pointer-events-none absolute top-0 left-0 h-0 w-0"
      >
        {Array.from({ length: track.count }, (_, i) => (
          <div
            key={i}
            data-above="false"
            className="absolute left-0 h-px w-px"
            style={{ top: `${track.gate + i * SENTINEL_GAP}px` }}
          />
        ))}
      </div>

      {/*
        Hover sensor for the top edge of the viewport.

        A retracted header has to be recoverable without scrolling up, and the
        conventional gesture is "push the pointer to the top of the screen". 64px
        is deep enough to catch a deliberate move and shallow enough that it
        never fires while reading.

        It must be a *sibling* placed before the header, because the recovery
        rule in globals.css is `.nav-sensor:hover ~ .nav-shell` — a sensor
        wrapping or inside the header could not work, since the header is
        `pointer-events: none` while retracted and would block its own hover.

        Inert on touch. There is no hover to trigger it, and a full-width 64px
        band across the top of a phone screen would otherwise swallow taps aimed
        at the content beneath it — so pointer events are only enabled from `md`.
      */}
      <div
        aria-hidden="true"
        className="nav-sensor pointer-events-none fixed inset-x-0 top-0 z-[var(--z-nav)] h-16 md:pointer-events-auto"
      />

      <header
        data-compact={compact}
        data-retracted={retracted}
        className="nav-shell fixed inset-x-0 top-0 z-[var(--z-nav)] flex justify-center px-[var(--space-page-x)] pt-4"
      >
        {/*
          ── Removed: the nav scrim ──

          A 128px gradient fading the page to `--color-bg` above the pill, so
          content dissolved on approach instead of sliding under a hard edge. It
          worked on black and it was indefensible on the two paper bands: the
          gradient is *black*, the band is #f4f2ec, and the header does not know
          what is behind it — so scrolling through `#foundation` or `#pricing` put
          a dark smear across the top of a white section. Visible in every
          before-shot of both bands.

          It is not replaced, because it is no longer needed for legibility. The
          scrim was introduced when `.nav-glass`'s `backdrop-filter` was being
          silently stripped by Lightning CSS and content passing underneath was
          transmitting about a third of its luminance. That bug is fixed (see the
          `@supports` block in globals.css), so the pill is now
          `rgba(6,6,7,0.86)` over a real 24px blur at 140% saturation, and nothing
          behind it is readable as text.

          The header also retracts during downward reading now, so in normal use
          content does not pass under it at all.
        */}
        <div
          className={cn(
            "relative flex w-full max-w-[var(--space-content-max)] items-center justify-between gap-6 rounded-[var(--radius-xl)] px-5 py-3",
            "transition-[background-color,border-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
            compact
              ? "nav-glass border border-[color:var(--color-border)] shadow-[var(--shadow-panel)]"
              : "border border-transparent bg-transparent",
          )}
        >
          {children}
        </div>
      </header>
    </>
  );
}
