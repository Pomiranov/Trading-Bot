import { cn } from "@/lib/utils";

/**
 * The cold beacon that marks the closed-testing state.
 *
 * ── Where it is used, and why it is one component ──
 *
 * "Closed testing" is stated in two visually unrelated places — the hero's
 * status pill and the footer status chip (as a `StatusChip` label). They had two
 * different treatments: the hero had no mark at all, and the footer had the
 * `muted` tone's flat grey dot. Owner direction is that every one of them
 * carries the same softly lit cold dot, so the geometry lives here rather than
 * being written twice and drifting.
 *
 * ── It is a lens, not a disc ──
 *
 * This used to be a 6px white square with `border-radius` and a cold
 * `box-shadow` behind it. Captured at 4× against the live hero, that renders as
 * a white blob with a blue smudge under it — no rim, no interior, no light
 * direction — which reads as a printing artefact rather than as a lit indicator.
 *
 * It now carries `.signal-lens`: a radial well lit from above, a conic rim masked
 * to a 1px annulus, and the aura. See the `--lens-*` block in
 * `styles/tokens/color.css` for the construction and for why the rim has to be
 * geometry rather than one more shadow.
 *
 * 8px rather than 6px, and the two pixels are what buy the structure: at 6px a
 * 1px rim leaves a 4px core, which is below the size at which a rim and a core
 * can be told apart on a 1× display. The dot sits in an `inline-flex` row with a
 * `gap`, so the two pixels widen the pill by two and shift nothing else.
 *
 * ── This is not the live dot, and the distinction is deliberate ──
 *
 * `.status-dot-live` (globals.css) is reserved for a genuine live state or the
 * depiction of one inside a labelled demo — the footer's old "Systems
 * operational" pulse was removed precisely because it was a live-status claim
 * with no telemetry behind it, and that line has not moved.
 *
 * This dot makes no claim about a running system. It marks the *programme's*
 * state: the product is in closed testing, which is a fact about how access is
 * granted and is stated in words immediately beside the dot in both locales. So
 * it gets its own, calmer treatment rather than the live ping:
 *
 *   • no expanding ring — the sonar ring reads as telemetry arriving
 *   • a slow 3.6s breathe on opacity and halo radius only, which reads as
 *     "powered on and waiting" rather than as "something just happened"
 *
 * ── Colour ──
 *
 * The blue never leaves the interior of an 8px circle and the aura immediately
 * around it. That is the permitted use of the signal colour — light, never ink.
 * See the doctrine at the top of tokens/color.css and the `cyan-as-ink` gate in
 * check-design-tokens.mjs.
 *
 * ── Motion ──
 *
 * `opacity` and `box-shadow` only, on an out-of-flow-safe inline-block with a
 * fixed size, so it can neither shift a baseline nor cost layout. The rim's
 * bright arc is *static* here: at 8px a travelling highlight is invisible and
 * still costs a repaint per frame, so the sweep from the reference is spent only
 * on the 40px pipeline node. Under `prefers-reduced-motion` the breathe is
 * dropped and the dot rests at its lit state — see `.signal-beacon` in
 * globals.css, which pins it rather than letting the global 0.01ms reset freeze
 * it on an arbitrary keyframe.
 */
export function SignalDot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("signal-lens signal-beacon inline-block size-2 shrink-0", className)}
    />
  );
}
