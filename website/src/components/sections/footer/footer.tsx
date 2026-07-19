import { getTranslations } from "next-intl/server";
import { Monogram } from "@/components/ui/monogram";

/**
 * The build-hash/deploy-timestamp line below is normally a banned
 * "version footer" tell (taste-skill 9.F) — explicit override here: the
 * client's brief asks for exactly this as a deliberate "we ship" signal,
 * not decoration.
 */
export async function Footer({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "footer" });

  const links = [
    { label: t("manifesto"), href: "#" },
    { label: t("system"), href: "#" },
    { label: t("research"), href: "#" },
    { label: t("contact"), href: "#" },
  ];

  const sha = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;
  const deployDate = buildTime
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(buildTime),
      )
    : null;

  return (
    <footer className="flex flex-col gap-8 border-t border-[color:var(--color-border)] px-[var(--space-page-x)] py-16 font-mono text-[13px]">
      <div className="flex items-center gap-3">
        <Monogram className="h-6 w-6 text-[color:var(--color-accent)]" />
        <span className="uppercase tracking-[0.1em] text-[color:var(--color-text-secondary)]">
          QuantFlow
        </span>
      </div>
      <nav className="flex flex-wrap gap-6">
        {links.map((link) => (
          <a
            key={link.label}
            href={link.href}
            className="text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
          >
            {link.label}
          </a>
        ))}
      </nav>
      <p className="text-[color:var(--color-text-tertiary)]">
        {t("buildLabel")} {sha}
        {deployDate ? ` · ${deployDate}` : null}
      </p>
    </footer>
  );
}
