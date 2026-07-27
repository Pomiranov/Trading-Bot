import { getTranslations } from "next-intl/server";
import { BrandMark } from "@/components/ui/brand-mark";
import { Link } from "@/lib/i18n/navigation";
import { ButtonLink } from "@/components/ui/button-link";
import { HeaderShell } from "./header-shell";
import { NavLinks } from "./nav-links";
import { MobileNav } from "./mobile-nav";

const LOCALES = [
  { code: "en" as const, label: "EN" },
  { code: "ru" as const, label: "RU" },
];

/**
 * Anchors target the section slug (`#dashboard`), never the heading id.
 * LenisProvider intercepts these and applies the shared NAV_OFFSET; a stale
 * target fails silently, so these must stay in step with the section ids in
 * `app/[locale]/page.tsx`.
 *
 * Five items, matching the reference. `#brokers`, `#strategies` and
 * `#foundation` are reachable from the footer instead — a header that lists
 * every section is a table of contents, not navigation.
 */
const LINKS = [
  { key: "dashboard", href: "#dashboard" },
  { key: "how", href: "#how-it-works" },
  { key: "safety", href: "#safety" },
  { key: "pricing", href: "#pricing" },
  { key: "faq", href: "#faq" },
] as const;

export async function SiteHeader({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "nav" });

  const otherLocale = LOCALES.find((l) => l.code !== locale) ?? LOCALES[0];
  const links = LINKS.map(({ key, href }) => ({ key, href, label: t(key) }));

  return (
    <HeaderShell>
      <a
        href="#hero"
        aria-label={t("brand")}
        className="flex shrink-0 items-center gap-2.5 rounded-[var(--radius-sm)] no-underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--color-accent)]"
      >
        <BrandMark size="sm" className="text-[color:var(--color-text-primary)]" />
        <span className="hidden font-mono text-[length:var(--text-caption)] tracking-[0.12em] text-[color:var(--color-text-primary)] uppercase sm:block">
          {t("brand")}
        </span>
      </a>

      {/* Visible from md (768px), not lg. Between 768 and 1023 there was ample
          room for the full row, and the hamburger was carrying it anyway. */}
      <NavLinks links={links} />

      <div className="flex items-center gap-3">
        {/*
          A single toggle, not two always-visible links.

          The previous version rendered both locales side by side plus a `w-px`
          hairline divider plus a gap — three separators inside 90px, and the
          hairline was an artefact rather than a designed element. One link that
          switches to the other language is smaller, quieter, and says the same
          thing. `aria-label` carries the meaning, since a bare "EN" is not a
          self-describing control.
        */}
        <Link
          href="/"
          locale={otherLocale.code}
          aria-label={`${t("brand")} — ${otherLocale.label}`}
          className="hidden rounded-[var(--radius-sm)] px-2 py-1.5 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] sm:block"
        >
          {otherLocale.label}
        </Link>

        <div className="hidden md:block">
          <ButtonLink
            href="#access"
            size="sm"
            analytics={{ target: "sandbox_access", location: "header" }}
          >
            {t("ctaShort")}
          </ButtonLink>
        </div>

        <MobileNav
          links={links}
          ctaLabel={t("ctaShort")}
          localeSwitchLabel={otherLocale.label}
          localeSwitchHref={`/${otherLocale.code}`}
          openLabel={t("menuOpen")}
          closeLabel={t("menuClose")}
        />
      </div>
    </HeaderShell>
  );
}
