import { getTranslations } from "next-intl/server";
import { Monogram } from "@/components/ui/monogram";
import { StatusPill } from "@/components/ui/status-pill";

/**
 * The old footer showed a green pulsing dot labelled "Systems operational"
 * with no telemetry behind it — a live-status claim the page could not
 * support. It now states the thing that is actually true and verifiable from
 * the outside: the project is in closed testing.
 */
export async function Footer({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "footer" });

  const links = [
    { label: t("linkHow"), href: "#how-it-works" },
    { label: t("linkFoundation"), href: "#foundation" },
    { label: t("linkSafety"), href: "#safety" },
    { label: t("linkStrategies"), href: "#strategies" },
    { label: t("linkContact"), href: "#access" },
  ];

  const sha = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;
  const deployDate = buildTime
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(buildTime),
      )
    : null;

  return (
    <footer className="border-t border-[color:var(--color-border)] px-[var(--space-page-x)] py-16">
      <div className="mx-auto flex w-full max-w-[var(--space-content-max)] flex-col gap-12">
        <div className="flex flex-col gap-10 md:flex-row md:justify-between">
          <div className="flex flex-col items-start gap-4">
            <div className="flex items-center gap-2.5">
              <Monogram className="size-6 text-[color:var(--color-text-primary)]" />
              <span className="font-mono text-[length:var(--text-caption)] tracking-[0.12em] text-[color:var(--color-text-primary)] uppercase">
                {t("brand")}
              </span>
            </div>
            <p className="max-w-[40ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
              {t("tagline1")}
              <br />
              {t("tagline2")}
            </p>
            <StatusPill tone="muted" label={t("status")} />
          </div>

          <nav aria-label="Footer" className="flex flex-col gap-1">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="-mx-2 rounded-[var(--radius-sm)] px-2 py-2 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        <div className="flex flex-col gap-4 border-t border-[color:var(--color-border)] pt-8">
          <p className="max-w-[80ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
            {t("legal")}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
            <span>{t("copyright")}</span>
            <span aria-hidden="true">·</span>
            <span>
              {t("buildLabel")} {sha}
              {deployDate ? ` · ${deployDate}` : null}
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
