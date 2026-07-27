import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A phone bezel around the Telegram signal card.
 *
 * The point is not decoration. "Оператор в кармане" is the claim, and a bare
 * card on a black page does not carry it — the reader has to be told that this
 * is a phone. Putting the artefact in a device reads instantly and lets the
 * copy stop explaining itself.
 *
 * Deliberately *not* a photorealistic mockup: no notch, no home indicator, no
 * status bar with a fake carrier and a fake time. Those are the details that
 * make a marketing page look like a template, and a fake 9:41 is the same
 * category of small lie as a fake win rate. This is a bezel, a screen and a
 * highlight — the geometry of a phone, nothing more.
 *
 * The frame is `aria-hidden` scaffolding; the card inside keeps all of its own
 * semantics and interactivity untouched.
 */
export function DeviceFrame({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "relative mx-auto w-full max-w-[320px] rounded-[var(--radius-2xl)] border border-[color:var(--color-border-strong)] bg-[color:var(--color-bg-elevated)] p-2.5 shadow-[var(--shadow-panel)]",
        className,
      )}
    >
      {/* Bezel highlight — one hairline along the top edge, the way light
          catches a real device. Inset so it follows the inner radius. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-8 top-px h-px bg-[color:var(--color-border-strong)]"
      />
      <div className="overflow-hidden rounded-[var(--radius-xl)]">{children}</div>
    </div>
  );
}
