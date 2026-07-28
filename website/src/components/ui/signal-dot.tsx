import { cn } from "@/lib/utils";

/**
 * The cold beacon that marks the closed-testing state.
 *
 * ── Where it is used, and why it is one component ──
 *
 * "Closed testing" is stated in two visually unrelated places — the hero eyebrow
 * (as the first clause of a mono metadata line) and the footer status chip (as a
 * `StatusChip` label). They had two different treatments: the hero had no mark
 * at all, and the footer had the `muted` tone's flat grey dot. Owner direction is
 * that every one of them carries the same softly lit cold dot, so the geometry
 * lives here rather than being written twice and drifting.
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
 * White core inside a cold halo. The cold blue arrives entirely as `box-shadow`,
 * which is the permitted use of the signal colour — light, never ink. See the
 * doctrine at the top of tokens/color.css and the `cyan-as-ink` gate in
 * check-design-tokens.mjs.
 *
 * ── Motion ──
 *
 * `opacity` and `box-shadow` only, on an out-of-flow-safe inline-block with a
 * fixed size, so it can neither shift a baseline nor cost layout. Under
 * `prefers-reduced-motion` the breathe is dropped and the dot rests at its lit
 * state — see `.signal-beacon` in globals.css, which pins it rather than letting
 * the global 0.01ms reset freeze it on an arbitrary keyframe.
 */
export function SignalDot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "signal-beacon inline-block size-1.5 shrink-0 rounded-[var(--radius-full)]",
        className,
      )}
    />
  );
}
