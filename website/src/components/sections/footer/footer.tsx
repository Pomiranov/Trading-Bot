import { getTranslations } from "next-intl/server";
import { BrandMark } from "@/components/ui/brand-mark";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/lib/i18n/navigation";

const LOCALES = [
  { code: "en" as const, label: "EN" },
  { code: "ru" as const, label: "RU" },
];

/**
 * Brand block plus three labelled link columns, per the reference.
 *
 * The previous footer stacked four links in one vertical list beside the brand
 * and was the thinnest block on the page — `py-16` (128px) sitting directly
 * under a section with 201.6px of padding, so the page did not so much end as
 * stop. It now uses the section scale and groups its links.
 *
 * ── Two claims that must not come back ──
 *
 * `status` reads "закрытое тестирование" and carries **no pulsing dot**. The
 * old footer showed a green pulsing dot labelled "Systems operational" with no
 * telemetry behind it — a live-status claim the page could not support. The
 * chip here states the thing that is actually true and externally verifiable.
 *
 * The build line is genuine provenance and stays, but it is now *hidden when
 * the SHA is `dev`* — which is every local and preview environment, where it
 * rendered a visible "Сборка dev" placeholder in the footer of an otherwise
 * finished page.
 */
export async function Footer({ locale }: { locale: string }) {
  const [t, nav] = await Promise.all([
    getTranslations({ locale, namespace: "footer" }),
    getTranslations({ locale, namespace: "nav" }),
  ]);

  const columns = [
    {
      heading: t("colProduct"),
      links: [
        { label: nav("dashboard"), href: "#dashboard" },
        { label: t("linkHow"), href: "#how-it-works" },
        { label: nav("pricing"), href: "#pricing" },
      ],
    },
    {
      heading: t("colTrust"),
      links: [
        { label: t("linkSafety"), href: "#safety" },
        { label: t("linkFoundation"), href: "#foundation" },
        { label: t("linkStrategies"), href: "#strategies" },
      ],
    },
    {
      heading: t("colMore"),
      links: [
        { label: nav("faq"), href: "#faq" },
        { label: t("linkContact"), href: "#access" },
      ],
    },
  ];

  const otherLocale = LOCALES.find((l) => l.code !== locale) ?? LOCALES[0];

  const sha = process.env.NEXT_PUBLIC_BUILD_SHA;
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;
  // Only a real SHA is provenance. "dev" is the absence of one.
  const showBuild = Boolean(sha) && sha !== "dev";
  const deployDate = buildTime
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(buildTime),
      )
    : null;

  return (
    <footer className="border-t border-[color:var(--color-border)] px-[var(--space-page-x)] py-[var(--space-section-y-tight)]">
      <div className="mx-auto flex w-full max-w-[var(--space-content-max)] flex-col gap-12">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,minmax(0,1fr))]">
          {/* ── Brand ── */}
          <div className="flex flex-col items-start gap-4">
            <div className="flex items-center gap-2.5">
              <BrandMark size="md" className="text-[color:var(--color-text-primary)]" />
              <span className="font-mono text-[length:var(--text-caption)] tracking-[0.12em] text-[color:var(--color-text-primary)] uppercase">
                {t("brand")}
              </span>
            </div>
            <p className="max-w-[36ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
              {t("tagline1")}
              <br />
              {t("tagline2")}
            </p>
            <StatusChip tone="muted" label={t("status")} />

            {/* Locale switch. The header's is hidden below sm, so on a phone
                this was previously the one place a visitor could not change
                language at all. */}
            <Link
              href="/"
              locale={otherLocale.code}
              aria-label={`${t("brand")} — ${otherLocale.label}`}
              className="-mx-2 rounded-[var(--radius-sm)] px-2 py-2 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
            >
              {otherLocale.label}
            </Link>
          </div>

          {/* ── Link columns ── */}
          {columns.map((col) => (
            <nav key={col.heading} aria-label={col.heading} className="flex flex-col gap-3">
              <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
                {col.heading}
              </p>
              <ul className="flex flex-col gap-1">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      // -mx-2/px-2/py-2 keeps the hit area at the 44px floor
                      // without changing the visual rhythm of the column.
                      className="-mx-2 inline-block rounded-[var(--radius-sm)] px-2 py-2 text-[length:var(--text-caption)] text-[color:var(--color-text-tertiary)] no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="flex flex-col gap-4 border-t border-[color:var(--color-border)] pt-8">
          <p className="max-w-[80ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
            {t("legal")}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
            <span>{t("copyright")}</span>
            {showBuild ? (
              <>
                <span aria-hidden="true">·</span>
                <span>
                  {t("buildLabel")} {sha}
                  {deployDate ? ` · ${deployDate}` : null}
                </span>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </footer>
  );
}
