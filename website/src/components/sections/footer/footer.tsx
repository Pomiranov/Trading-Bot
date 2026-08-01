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

  /**
   * Every `href` here must resolve to a live section id in
   * `app/[locale]/page.tsx`. A stale anchor fails silently — the Lenis
   * interceptor simply finds no target and nothing happens — so this list and
   * the page's section order have to be changed together.
   *
   * `#strategies` was dropped with the strategy-lab section; `#telegram` takes
   * its place in the product column, and the trust column is two links rather
   * than three. Padding it back to three for symmetry would mean inventing a
   * destination.
   */
  const columns = [
    {
      heading: t("colProduct"),
      links: [
        { label: nav("dashboard"), href: "#dashboard" },
        { label: t("linkHow"), href: "#how-it-works" },
        { label: t("linkTelegram"), href: "#telegram" },
        { label: nav("pricing"), href: "#pricing" },
      ],
    },
    {
      heading: t("colTrust"),
      links: [
        { label: t("linkSafety"), href: "#safety" },
        { label: t("linkFoundation"), href: "#foundation" },
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
            {/* `beacon`, not `pulse`. This is the closed-testing badge, and
                owner direction is that every one of them carries the same cold
                dot. It marks the programme's state, not a live system — see the
                note on the prop, which restates the boundary the footer's old
                "Systems operational" pulse was removed for. */}
            <StatusChip tone="muted" label={t("status")} beacon />

            {/* Locale switch. The header's is hidden below sm, so on a phone
                this was previously the one place a visitor could not change
                language at all — which is also why its hit area matters more
                than its size suggests. At 11px mono with `py-2` it measured
                32×34, the smallest target on the page; `min-h-11` and a 44px
                minimum width put it on the floor without enlarging the label.

                `justify-start`, not `justify-center`: centring an 22px label in a
                44px box pushed "EN" 11px right of the column's left edge, where
                the tagline and the brand above it start. A hit area is allowed to
                be wider than its label — it is not allowed to move it. */}
            <Link
              href="/"
              locale={otherLocale.code}
              aria-label={`${t("brand")} — ${otherLocale.label}`}
              className="-mx-2 inline-flex min-h-11 min-w-11 items-center justify-start rounded-[var(--radius-sm)] px-2 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
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
              {/* `gap-0`: each link is its own 44px row and they sit flush.
                  With `gap-1` and the negative margin the boxes below needed to
                  keep the old rhythm, consecutive targets *overlapped* by 4px —
                  measured 39px of effective height each, with the top and bottom
                  strip of every link belonging to its neighbour. A 44px row that
                  another target eats into is not a 44px target. */}
              <ul className="flex flex-col">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      // The hit area is the 44px floor by *construction*, not by
                      // arithmetic. `py-2` was meant to reach it and did not:
                      // 13px of caption at 1.5 line-height is 19.5px, plus 16px
                      // of padding, is 35.5 — measured at 37px, seven short, on
                      // seven links. `min-h-11` states the floor instead of
                      // computing it, so it cannot drift when the type scale
                      // moves. No negative vertical margin — see the note on the
                      // list above for why clawing the height back overlapped the
                      // targets; the column is 3px per row looser instead.
                      className="-mx-2 inline-flex min-h-11 items-center rounded-[var(--radius-sm)] px-2 text-[length:var(--text-caption)] text-[color:var(--color-text-tertiary)] no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
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
