/**
 * The faint technical grid behind the hero panel.
 *
 * Two `repeating-linear-gradient`s rather than an SVG pattern or an image: it
 * is one paint, no request, no extra DOM, and it scales to any panel size
 * without re-tiling artefacts.
 *
 * Masked to fade out at the edges so the grid has no visible boundary. A grid
 * that stops in a hard line reads as a texture someone pasted in; one that
 * dissolves reads as depth. The alpha is deliberately at the threshold of
 * perception — if you can count the cells without looking for them, it is too
 * strong.
 *
 * `aria-hidden` and pointer-events-none: it is atmosphere, not content.
 */
export function GridBackplate({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 ${className ?? ""}`}
      style={{
        backgroundImage: `repeating-linear-gradient(to right, var(--color-border) 0 1px, transparent 1px 64px), repeating-linear-gradient(to bottom, var(--color-border) 0 1px, transparent 1px 64px)`,
        opacity: 0.5,
        maskImage:
          "radial-gradient(ellipse 80% 70% at 50% 45%, #000 0%, transparent 78%)",
        WebkitMaskImage:
          "radial-gradient(ellipse 80% 70% at 50% 45%, #000 0%, transparent 78%)",
      }}
    />
  );
}
