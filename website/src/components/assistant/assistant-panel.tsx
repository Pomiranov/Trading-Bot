import type { Ref } from "react";

export interface AssistantPanelProps {
  id: string;
  open: boolean;
  title: string;
  body: string;
  closeLabel: string;
  onClose: () => void;
  /** Focus lands here when the panel opens, and the panel is what Escape closes. */
  ref?: Ref<HTMLDivElement>;
}

/**
 * The placeholder panel behind the orb.
 *
 * ── Why there is a panel at all, when the reference has none ──
 *
 * `Vois Asistent.mp4` is a sphere and nothing else, so the orb is built to it
 * exactly. But a button that visibly responds to a press and then does nothing is
 * worse than no button: the reader concludes the page is broken rather than that
 * the feature is unreleased. Owner direction allows a minimal placeholder for
 * exactly this reason, with two hard limits, both honoured here:
 *
 *   • no fabricated assistant replies, and nothing shaped like a chat transcript
 *   • no imitation of an AI product that is not connected
 *
 * So the panel states the truth in two sentences — it is not available yet, and
 * here is what it will do — and offers no input field, because an input that
 * cannot be submitted is the same broken promise one level deeper.
 *
 * ── Why a disclosure and not a modal ──
 *
 * `role="dialog"` with `aria-modal` would oblige a focus trap, a scroll lock and
 * an inert background. All three are correct for something a reader must deal
 * with before continuing, and all three are wrong for one paragraph of "coming
 * soon" — it would take the page hostage to deliver an aside.
 *
 * It is a plain disclosure instead: `aria-expanded` and `aria-controls` on the
 * orb, this panel as the controlled region. Escape closes it, a click outside
 * closes it, and focus moves here on open and back to the orb on close — which
 * is the behaviour a reader expects without any of the confinement.
 *
 * `tabIndex={-1}` is what lets focus land on the container itself, so a screen
 * reader reads the heading and the body from the top rather than starting at the
 * close button.
 *
 * ── The seam ──
 *
 * When the assistant is connected, this file is what gets replaced — a thread
 * view and a composer, mounted in the same slot, opened by the same orb. Nothing
 * about `assistant-orb.tsx` or the launcher's open/close contract has to change.
 */
export function AssistantPanel({
  id,
  open,
  title,
  body,
  closeLabel,
  onClose,
  ref,
}: AssistantPanelProps) {
  return (
    <div
      id={id}
      ref={ref}
      tabIndex={-1}
      // `hidden` rather than an unmounted subtree: the panel is the target of
      // `aria-controls`, and that reference must resolve to an element in the DOM
      // whether or not it is showing. `hidden` also keeps it out of the tab order
      // and the accessibility tree for free, which is the whole job `inert` would
      // otherwise be doing by hand.
      hidden={!open}
      data-open={open}
      className="assistant-panel"
    >
      <div className="flex items-start justify-between gap-4">
        <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] font-medium text-[color:var(--color-text-primary)]">
          {title}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label={closeLabel}
          className="assistant-panel__close"
        >
          {/* A drawn glyph, not a `×` character: the multiplication sign renders
              at a different weight and optical centre in each of the two families
              this page loads, and at 10px that difference is visible. */}
          <svg viewBox="0 0 10 10" aria-hidden="true" focusable="false" className="size-2.5">
            <path
              d="M1 1 L9 9 M9 1 L1 9"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
        </button>
      </div>

      <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
        {body}
      </p>
    </div>
  );
}
