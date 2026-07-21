import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

export async function SandboxSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "sandbox" });

  const points = [t("point1"), t("point2"), t("point3")];

  return (
    <section
      aria-labelledby="sandbox-heading"
      className="px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <Reveal>
        <div
          className="mx-auto flex max-w-[1040px] flex-col gap-10 p-8 md:p-14 relative overflow-hidden rounded-2xl"
          style={{
            background: "rgba(10,10,12,0.8)",
            backdropFilter: "blur(24px)",
            border: "1px solid rgba(255,255,255,0.07)",
            boxShadow: "0 8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)",
          }}
        >
          {/* Background glow */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 top-0 w-[400px] h-[400px] rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(255,138,30,0.06) 0%, transparent 65%)",
              filter: "blur(40px)",
            }}
          />

          <div className="relative flex flex-col gap-5 md:flex-row md:items-start md:justify-between md:gap-12">
            <div className="flex flex-col gap-4 md:max-w-[55%]">
              <SectionHeading id="sandbox-heading" className="max-w-[24ch]">
                {t("heading")}
              </SectionHeading>
              <p
                className="max-w-[54ch] text-[15px] leading-relaxed"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {t("intro")}
              </p>
            </div>

            {/* Feature points */}
            <ul className="relative flex flex-col gap-0 divide-y md:max-w-[40%]"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}
            >
              {points.map((point, i) => (
                <li
                  key={point}
                  className="flex items-start gap-3 py-4 first:pt-0 last:pb-0 text-[14px] leading-relaxed"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  <span
                    className="shrink-0 font-mono text-[11px] tabular-nums mt-0.5"
                    style={{ color: "var(--color-accent)" }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>

          {/* Bottom stat bar */}
          <div
            className="relative flex flex-wrap gap-6 pt-6"
            style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
          >
            {[
              { label: t("statSignalPath"), value: t("statSignalPathValue") },
              { label: t("statFillSim"), value: t("statFillSimValue") },
              { label: t("statRiskMgr"), value: t("statRiskMgrValue") },
            ].map(({ label, value }) => (
              <div key={label} className="flex flex-col gap-0.5">
                <span
                  className="font-mono text-[10px] uppercase tracking-[0.14em]"
                  style={{ color: "rgba(255,255,255,0.3)" }}
                >
                  {label}
                </span>
                <span
                  className="font-mono text-[12px]"
                  style={{ color: "rgba(255,255,255,0.6)" }}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  );
}
