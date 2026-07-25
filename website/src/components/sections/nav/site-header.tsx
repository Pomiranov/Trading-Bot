import { getTranslations } from "next-intl/server";
import { Monogram } from "@/components/ui/monogram";
import { Link } from "@/lib/i18n/navigation";
import { HeaderCta } from "./header-cta";
import { MobileNav } from "./mobile-nav";

const LOCALES = [
  { code: "en" as const, label: "EN" },
  { code: "ru" as const, label: "RU" },
];

const LINK_KEYS = ["product", "engine", "telegram", "pricing", "faq"] as const;
const LINK_TARGETS: Record<(typeof LINK_KEYS)[number], string> = {
  product: "#dashboard-preview-heading",
  engine: "#engine-pipeline-heading",
  telegram: "#telegram-bot-heading",
  pricing: "#pricing-heading",
  faq: "#faq-heading",
};

export async function SiteHeader({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "nav" });

  const otherLocale = LOCALES.find((l) => l.code !== locale) ?? LOCALES[0];

  const mobileLinks = LINK_KEYS.map((key) => ({
    key,
    label: t(key),
    href: LINK_TARGETS[key],
  }));

  return (
    <header className="fixed inset-x-0 top-0 z-[var(--z-nav)] flex justify-center px-[var(--space-page-x)] pt-4">
      <div
        className="flex w-full max-w-[1280px] items-center justify-between gap-6 px-5 py-3"
        style={{
          borderRadius: "0.75rem",
          border: "1px solid rgba(255,255,255,0.07)",
          background: "rgba(5,5,5,0.82)",
          backdropFilter: "blur(28px)",
          WebkitBackdropFilter: "blur(28px)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04), 0 4px 24px rgba(0,0,0,0.3)",
        }}
      >
        {/* Logo */}
        <a
          href="#hero-heading"
          aria-label="QuantFlow"
          className="flex items-center gap-2.5 no-underline shrink-0"
        >
          <Monogram
            className="h-5 w-5"
            style={{ color: "var(--color-accent)" }}
          />
          <span
            className="hidden font-mono text-[13px] uppercase tracking-[0.12em] sm:block"
            style={{ color: "rgba(255,255,255,0.65)" }}
          >
            QuantFlow
          </span>
        </a>

        {/* Primary nav — desktop only */}
        <nav aria-label="Primary" className="hidden items-center gap-7 lg:flex">
          {LINK_KEYS.map((key) => (
            <a
              key={key}
              href={LINK_TARGETS[key]}
              className="font-mono text-[11px] uppercase tracking-[0.1em] transition-colors duration-150 hover:text-white"
              style={{ color: "rgba(255,255,255,0.4)", textDecoration: "none" }}
            >
              {t(key)}
            </a>
          ))}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Language switcher — desktop */}
          <nav
            aria-label="Language"
            className="hidden items-center gap-3 font-mono text-[11px] uppercase tracking-[0.1em] sm:flex"
          >
            {LOCALES.map(({ code, label }) => (
              <Link
                key={code}
                href="/"
                locale={code}
                aria-current={locale === code ? "true" : undefined}
                className="transition-colors duration-150"
                style={{
                  color: locale === code ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.3)",
                  textDecoration: "none",
                }}
              >
                {label}
              </Link>
            ))}
          </nav>

          <div
            className="hidden h-4 w-px sm:block lg:block"
            style={{ background: "rgba(255,255,255,0.1)" }}
          />

          {/* Desktop CTA */}
          <div className="hidden lg:block">
            <HeaderCta label={t("requestAccess")} />
          </div>

          {/* Mobile nav (includes CTA inside dropdown) */}
          <MobileNav
            links={mobileLinks}
            ctaLabel={t("requestAccess")}
            localeSwitchLabel={otherLocale.label}
            localeSwitchHref={`/${otherLocale.code}`}
            openLabel={t("menuOpen")}
            closeLabel={t("menuClose")}
          />
        </div>
      </div>
    </header>
  );
}
