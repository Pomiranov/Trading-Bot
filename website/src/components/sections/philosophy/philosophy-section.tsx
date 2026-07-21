import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

export async function PhilosophySection({ locale }: { locale: string }) {
  const [blocks, t] = await Promise.all([
    contentSource.getPhilosophyBlocks(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  const weight = [
    { color: "rgba(255,255,255,0.45)", size: "15px", leading: "1.7" },
    { color: "rgba(255,255,255,0.7)", size: "16px", leading: "1.65" },
    { color: "rgba(255,255,255,0.88)", size: "17px", leading: "1.62", fontWeight: "450" },
  ];

  return (
    <section
      aria-labelledby="philosophy-heading"
      className="relative px-[var(--space-page-x)] py-[var(--space-section-y)] overflow-hidden"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(255,138,30,0.03) 0%, transparent 60%)",
          filter: "blur(80px)",
        }}
      />

      <div className="mx-auto flex max-w-[960px] flex-col gap-16 relative">
        <div className="flex items-start justify-between gap-8">
          <Reveal>
            <div className="flex flex-col gap-3">
              <span
                className="font-mono text-[10px] uppercase tracking-[0.18em]"
                style={{ color: "var(--color-accent)", opacity: 0.7 }}
              >
                01
              </span>
              <SectionHeading id="philosophy-heading" className="max-w-[20ch]">
                {t("philosophy")}
              </SectionHeading>
            </div>
          </Reveal>
        </div>

        <div className="flex flex-col">
          {blocks.map((block, i) => (
            <Reveal key={block.id} index={i}>
              <div
                className="grid gap-6 py-9 md:grid-cols-[200px_1fr]"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
              >
                <div className="flex flex-col gap-1.5">
                  <span
                    className="font-mono tabular-nums text-[9px] uppercase tracking-[0.16em]"
                    style={{ color: "rgba(255,138,30,0.6)" }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3
                    className="text-[13px] font-medium leading-snug"
                    style={{ color: "rgba(255,255,255,0.55)", letterSpacing: "-0.01em" }}
                  >
                    {block.heading}
                  </h3>
                </div>
                <div
                  className="max-w-[58ch]"
                  style={{
                    color: weight[i]?.color ?? weight[weight.length - 1].color,
                    fontSize: weight[i]?.size ?? weight[weight.length - 1].size,
                    lineHeight: weight[i]?.leading ?? "1.65",
                    fontWeight: weight[i]?.fontWeight ?? "400",
                  }}
                >
                  {block.body}
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
