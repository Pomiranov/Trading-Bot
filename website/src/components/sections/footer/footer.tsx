import { getTranslations } from "next-intl/server";
import { Monogram } from "@/components/ui/monogram";

export async function Footer({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "footer" });

  const links = [
    { label: t("manifesto"), href: "#philosophy-heading" },
    { label: t("system"), href: "#engine-pipeline-heading" },
    { label: t("research"), href: "#strategy-layer-heading" },
    { label: t("contact"), href: "#cta-heading" },
  ];

  const sha = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;
  const deployDate = buildTime
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(buildTime),
      )
    : null;

  return (
    <footer
      className="relative overflow-hidden px-[var(--space-page-x)] py-16 font-mono text-[13px]"
      style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
    >
      {/* Ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 40% 60% at 20% 50%, rgba(255,138,30,0.04), transparent)",
        }}
      />

      <div className="relative flex flex-col gap-10 md:flex-row md:items-end md:justify-between">
        {/* Brand */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2.5">
            <Monogram
              className="h-6 w-6"
              style={{ color: "var(--color-accent)" }}
            />
            <span
              className="uppercase tracking-[0.12em]"
              style={{ color: "rgba(255,255,255,0.6)" }}
            >
              QuantFlow
            </span>
          </div>
          <p
            className="max-w-[36ch] text-[12px] leading-relaxed"
            style={{ color: "rgba(255,255,255,0.3)" }}
          >
            Institutional-grade algorithmic trading.
            <br />
            Built on statistical belief, not invented alpha.
          </p>
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <span
              className="size-1.5 rounded-full"
              style={{
                backgroundColor: "var(--color-success)",
                boxShadow: "0 0 6px var(--color-success)",
              }}
            />
            <span
              className="text-[10px] uppercase tracking-[0.14em]"
              style={{ color: "rgba(255,255,255,0.3)" }}
            >
              Systems operational
            </span>
          </div>
        </div>

        {/* Links */}
        <nav className="flex flex-col gap-2.5">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[11px] uppercase tracking-[0.1em] transition-colors duration-200 hover:text-white/70"
              style={{ color: "rgba(255,255,255,0.3)", textDecoration: "none" }}
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Build info */}
        <div className="flex flex-col gap-1.5">
          <p
            className="text-[10px] uppercase tracking-[0.1em]"
            style={{ color: "rgba(255,255,255,0.2)" }}
          >
            {t("buildLabel")} {sha}
            {deployDate ? ` · ${deployDate}` : null}
          </p>
          <p
            className="text-[10px] uppercase tracking-[0.1em]"
            style={{ color: "rgba(255,255,255,0.15)" }}
          >
            © 2026 QuantFlow. Private beta.
          </p>
        </div>
      </div>
    </footer>
  );
}
