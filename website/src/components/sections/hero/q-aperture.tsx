import { BrandMark } from "@/components/ui/brand-mark";

/**
 * The hero instrument: the Quant mark inside a set of tilted orbital paths.
 *
 * ── What this replaces ──
 *
 * The previous visual wrapped a flat diagram in application-window chrome — a
 * title bar with the mark and a "ПУТЬ РЕШЕНИЯ" label, a mode pill, then the
 * aperture, then a six-cell step rail restating information the pipeline
 * section gives properly 900px later. Three layers of UI framing around what
 * the reference presents as one free-floating object, and the object itself was
 * three coplanar circles at 6/9/13% white — measured at roughly 640×440 it read
 * as a mostly-empty dark rectangle.
 *
 * This is the object with nothing around it: no frame, no title bar, no status
 * pill, no step rail.
 *
 * ── The claim-free contract ──
 *
 * Non-negotiable, and the reason this is orbits rather than anything else.
 * There is no chart, no curve, no plotted series, no counter, no percentage and
 * no rising line anywhere in here. A moving line on a trading site is a
 * performance claim regardless of the caption underneath it, and that is
 * precisely what an earlier hero was corrected for. Orbits carry "a system that
 * is running" without asserting a single thing about outcomes.
 *
 * ── What the polish pass took out, and why it is not coming back ──
 *
 * Three concentric white measurement rings, four quadrant ticks, a horizontal
 * scan trace and three axis labels ("Вход" / "Правило" / "Заявка") around the
 * outside.
 *
 * Owner direction, and one note covers all of them: they read as *technical
 * markup laid over the object* rather than as the object. The rings were the
 * instrument's "fixed reference", the ticks existed to anchor the labels, and
 * the labels named the three stages `#how-it-works` documents properly 900px
 * later — so the hero was captioning itself with a diagram key while the orbits
 * were already saying the only thing this visual is for: a system that is
 * running. Stripped back, it is one object with one light on it, which is the
 * whole brief.
 *
 * If a fixed reference is ever wanted here again it has to be composed with the
 * orbits rather than drawn as a target over them, and it must not need labels
 * to be legible. `.hero-ring` / `.hero-scan` and their keyframes were deleted
 * from globals.css with this.
 *
 * ── Motion ──
 *
 * Two loops, both compositor-only (`transform` / `opacity`), so this cannot
 * shift layout or cost LCP:
 *   • three orbit groups rotating at 32 / 46 / 61s — coprime, so they never
 *     resync into one visible beat
 *   • the core bloom breathing over 8s
 *
 * No keyframe uses `animation-fill-mode`, so the base style *is* the resting
 * state. Under `prefers-reduced-motion` the global reset collapses duration to
 * 0.01ms and iteration count to 1, and the instrument simply reverts to its
 * base style: still, complete, legible. That is the whole reduced-motion story
 * here, and it is why no base value may be a mid-animation value.
 *
 * Server-rendered, zero client JS, no external asset.
 */
export function QAperture() {
  return (
    // One fluid width rather than a `max-w-[…] sm: lg:` chain. The chain was
    // the first attempt and it silently capped at the `sm` value — arbitrary
    // values in three breakpoint variants are fragile to emit-order, and the
    // failure mode is a quietly undersized instrument rather than an error.
    // A clamp has no ordering to get wrong and tracks the column continuously.
    <div className="relative isolate mx-auto flex aspect-square w-full max-w-[clamp(215px,38vw,520px)] items-center justify-center">
      {/* Ambient cold pool behind everything. The single largest use of the
          signal colour on the page, and still only 20% alpha at its centre,
          falling to nothing by 68%. It is light, not a surface. */}
      <div
        aria-hidden="true"
        className="aperture-core pointer-events-none absolute inset-0 -z-10"
        style={{ background: "var(--glow-aperture)" }}
      />

      <svg
        viewBox="0 0 400 400"
        className="h-full w-full overflow-visible"
        role="presentation"
        aria-hidden="true"
      >
        <defs>
          {/* Each orbit fades along its length so the ellipse reads as a path
              travelling *behind* the aperture and back, rather than as a flat
              ring drawn on top of it. This is what gives the composition depth
              without any 3D transform. */}
          <linearGradient id="qa-orbit" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--color-signal)" stopOpacity="0.05" />
            <stop offset="35%" stopColor="var(--color-signal)" stopOpacity="0.45" />
            <stop offset="65%" stopColor="var(--color-signal-core)" stopOpacity="0.7" />
            <stop offset="100%" stopColor="var(--color-signal)" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        {/* ── Orbits ──
            Three ellipses at different inclinations. Each sits in its own <g>
            that carries the rotation, so the animation spins the *path* while
            the ellipse keeps its tilt — an orbit seen at an angle, not a
            spinning wheel. transform-box/transform-origin are set so the
            rotation is about the viewBox centre in every engine. */}
        <g style={{ transformBox: "view-box", transformOrigin: "200px 200px" }}>
          <g className="orbit-a" style={{ transformBox: "view-box", transformOrigin: "200px 200px" }}>
            <ellipse
              cx="200"
              cy="200"
              rx="178"
              ry="66"
              fill="none"
              stroke="url(#qa-orbit)"
              strokeWidth="1.25"
              transform="rotate(-24 200 200)"
            />
            {/* One node riding the path. Positioned at the ellipse's extremity
                and carried by the same rotation, so it stays on its orbit
                without any per-frame maths. */}
            <circle cx="378" cy="200" r="3" fill="var(--color-signal-core)" opacity="0.85" transform="rotate(-24 200 200)" />
          </g>

          <g className="orbit-b" style={{ transformBox: "view-box", transformOrigin: "200px 200px" }}>
            <ellipse
              cx="200"
              cy="200"
              rx="140"
              ry="112"
              fill="none"
              stroke="url(#qa-orbit)"
              strokeWidth="1"
              transform="rotate(38 200 200)"
            />
            <circle cx="340" cy="200" r="2.5" fill="var(--color-signal-core)" opacity="0.7" transform="rotate(38 200 200)" />
          </g>

          <g className="orbit-c" style={{ transformBox: "view-box", transformOrigin: "200px 200px" }}>
            <ellipse
              cx="200"
              cy="200"
              rx="112"
              ry="44"
              fill="none"
              stroke="url(#qa-orbit)"
              strokeWidth="1"
              transform="rotate(74 200 200)"
            />
          </g>
        </g>

        {/*
          ── Removed: the exit vector and its node ──

          A dashed path ran from the centre out to (330, 300) and terminated in
          a filled white dot with a ring around it, outside the outermost
          measurement circle. The intent was "a decision leaving the
          instrument".

          It did not read that way. Every other element here is concentric or
          orbital, so a single diagonal breaking out to a lone dot in the
          lower-right read as a stray artefact — a leftover from a diagram
          rather than part of the object — which is exactly the note it was
          removed on. Owner direction, and the aperture is cleaner without it.

          Do not reinstate it as decoration. If a directional "exit" is ever
          wanted here it has to be composed with the orbits, not laid across
          them. `.hero-vector` / `@keyframes qf-vector-flow` were deleted from
          globals.css with it.

          The white measurement rings, the quadrant ticks and the scan trace
          that used to sit here went the same way in a later pass, for the same
          reason — see the note at the top of this file.
        */}
      </svg>

      {/*
        The mark sits on top as its own element rather than nested inside the
        SVG above: a nested <svg> inherits the parent's viewBox scaling in ways
        that differ between engines, and BrandMark is also used at 16px in the
        nav, so it has to stay a standalone component.
      */}
      <BrandMark
        aria-hidden="true"
        glow
        className="pointer-events-none absolute top-1/2 left-1/2 size-[22%] -translate-x-1/2 -translate-y-1/2 text-[color:var(--color-text-primary)]"
      />

      {/*
        ── Removed: the axis labels ──

        "Вход" / "Правило" / "Заявка", pinned to the left, top and right
        quadrant ticks. They were defended here as "the reason this is a diagram
        of a decision rather than an abstract orbit animation" — which was the
        mistake. The hero does not want a diagram; the headline and the subline
        beside it make the argument, and `#how-it-works` names those exact three
        stages properly, with a sentence each.

        What they actually did was force the ticks to exist so they had
        something to hang on, which forced the rings to exist so the ticks had a
        reference — three layers of markup standing up one caption. All of it is
        gone together. `hero.apertureIn/Rule/Out` were deleted from both message
        catalogues.
      */}
    </div>
  );
}
