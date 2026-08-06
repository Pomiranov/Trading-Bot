import { GridBackplate } from "@/components/ui/grid-backplate";

/**
 * The background of a paper band: the page's grid, at full section height, plus
 * the cold-white pool that follows the pointer across it.
 *
 * ── The defect it repairs ──
 *
 * `#foundation` and `#pricing` had a grid only inside the 176–256px
 * `BandTransition` above them. Below that the paper was bare for the remaining
 * ~900px, so the geometry that runs through the rest of the page arrived at the
 * band, crossed 200px of it, and stopped. Measured at 1440 that put a visible
 * horizon a fifth of the way into each band — which is most of why a light
 * section read as a white block someone inserted rather than as the same page
 * changing material.
 *
 * Running the grid the whole height means the transition band is no longer where
 * the grid *is*; it is only where the grid changes ink. That is the difference
 * between two materials butted together and one material changing state, and it
 * is the same argument `ui/band-transition.tsx` makes for putting a grid inside
 * the ramp at all.
 *
 * ── Why the mask is `band` and not `panel` ──
 *
 * It fades at the left and right margins only, and is held at full strength top
 * and bottom. A vertical fade would put a soft horizon inside the section — the
 * exact artefact being removed — and would also leave a gap between this grid
 * and the band's own, which sits directly above and below it. Held flat, the
 * three join into one continuous field down the page.
 *
 * ── Requires a field ──
 *
 * The pointer layers read `--signal-x/y/on` from an ancestor `SignalField`,
 * which on these sections is the `<section>` itself (`field` on `ui/section.tsx`).
 * Without one the variables are unset, `--signal-on` falls back to 0, and both
 * layers are fully transparent — so this is exactly a static grid on touch,
 * under reduced motion, and with no JS. Neither layer lays out.
 */
export function PaperField() {
  return (
    <>
      <GridBackplate tone="paper" mask="band" signal />
      {/* The ground lift. Not masked to the grid, because the brief is that the
          area *around* the cards responds, and hairlines alone cannot carry
          that on a light ground. See `.signal-field__bloom` in globals.css for
          why it is held as low as it is. */}
      <div aria-hidden="true" className="signal-field__bloom" />
    </>
  );
}
