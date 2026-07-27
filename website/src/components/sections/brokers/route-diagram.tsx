import { SignalLine } from "@/components/ui/signal-line";

/**
 * Signal → gate → risk → broker, as topology.
 *
 * The brokers section was a specification list: three cards whose only
 * differentiator was an 11px status pill. This is what ties it back to the
 * pipeline — it says *where in the decision path a broker sits*, which is the
 * thing that makes "execution" mean something.
 *
 * ── What it deliberately does not claim ──
 *
 * No throughput, no latency, no fill rate, no success percentage, no volume.
 * Four labelled nodes and the order between them, nothing else. A diagram on a
 * trading site is the easiest place in the world to imply performance by
 * accident, so there are no figures on it at all and the caption says so
 * explicitly.
 *
 * Horizontal at md and up; vertical below, because a horizontally-drawn
 * four-node diagram at 390px would need a scroller and this page does not add
 * scrollers it can avoid.
 */
export function RouteDiagram({ steps }: { steps: readonly string[] }) {
  return (
    <ol className="flex flex-col gap-3 md:flex-row md:items-center md:gap-0">
      {steps.map((step, i) => (
        <li key={step} className="flex items-center gap-3 md:flex-1 md:flex-col md:items-stretch md:gap-0">
          {/* Connector before every node except the first. At md it is the
              horizontal SignalLine; below md the nodes simply stack and the
              line is hidden, since a vertical hairline between four full-width
              rows adds nothing. */}
          {i > 0 ? (
            <div className="hidden md:block">
              <SignalLine orientation="horizontal" />
            </div>
          ) : null}

          <div className="flex items-center gap-3 md:justify-center">
            {/* Stacked-layout node marker. An outlined white dot, not a filled
                cyan one: a coloured dot sitting beside a step name reads as a
                *status*, and cold blue is explicitly never a status colour. The
                cyan on this diagram belongs to the connector between nodes,
                which is decorative geometry. The glow is the only signal light
                the marker gets. */}
            <span
              aria-hidden="true"
              className="size-1.5 shrink-0 rounded-[var(--radius-full)] border border-[color:var(--color-border-strong)] md:hidden"
              style={{ boxShadow: "var(--glow-signal-sm)" }}
            />
            <span className="rounded-[var(--radius-full)] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3.5 py-1.5 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase">
              {step}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}
