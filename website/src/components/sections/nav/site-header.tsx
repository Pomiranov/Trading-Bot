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
 * Five items, matching the reference. `#foundation` and `#telegram` are reachable
 * from the footer instead — a header that lists every section is a table of
 * contents, not navigation.
 *
 * `#brokers` and `#strategies` used to be in that footer list too; both sections
 * were removed from the page, and the links went with them. See the note in
 * `app/[locale]/page.tsx` for where their disclosures now live.
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
      {/*
        ── Two fixes, one element, and they fix each other ──

        The wordmark was hidden below `sm` and the link was therefore 20×20: the
        smallest target on the page, and the brand reduced to a bare glyph on the
        one device where the header has nothing else in it. Measured at 390px the
        pill held a 20px mark and a 44px hamburger inside 320px — roughly 250px of
        empty glass, which is most of why the mobile header read as unfinished.

        Showing the wordmark at every width fills that space with the thing the
        space is for, and it takes the link to ~90px wide at the same stroke. The
        height is stated as a `min-h-11` floor rather than left to the mark's own
        20px, so the target clears 44 without the pill growing — `-my-*` is not
        needed because the pill is already 62px tall and this sits inside it.
      */}
      <a
        href="#hero"
        aria-label={t("brand")}
        className="flex min-h-11 shrink-0 items-center gap-2.5 rounded-[var(--radius-sm)] no-underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--color-accent)]"
      >
        <BrandMark size="sm" className="text-[color:var(--color-text-primary)]" />
        <span className="font-mono text-[length:var(--text-caption)] tracking-[0.12em] text-[color:var(--color-text-primary)] uppercase">
          {t("brand")}
        </span>
      </a>

      <NavLinks links={links} label={t("primaryNavLabel")} />

      <div className="flex items-center gap-3">
        {/*
          A single toggle, not two always-visible links.

          The previous version rendered both locales side by side plus a `w-px`
          hairline divider plus a gap — three separators inside 90px, and the
          hairline was an artefact rather than a designed element. One link that
          switches to the other language is smaller, quieter, and says the same
          thing. `aria-label` carries the meaning, since a bare "EN" is not a
          self-describing control — and it states the *action* ("Switch
          language: …"), not just the brand and a code.

          Hit area follows the footer switch's pattern: `min-h-11 min-w-11`
          puts the ~30×35 target on the 44px floor without enlarging the label,
          `-mx-1.5` gives the width back so the row's spacing reads unchanged.
          No `-my-*` needed — the pill is tall enough already.
        */}
        <Link
          href="/"
          locale={otherLocale.code}
          aria-label={t("localeSwitchAction")}
          className="-mx-1.5 hidden min-h-11 min-w-11 items-center justify-center rounded-[var(--radius-sm)] px-2 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] sm:inline-flex"
        >
          {otherLocale.label}
        </Link>

        {/* ── The default size, not `sm`, and it costs nothing ──
            At `sm` this rendered 36px tall. That clears WCAG 2.2's 24px target-size
            minimum, but the brief's floor for any control a finger can reach is
            44px, and the block is `hidden lg:block` — so it *is* on screen at
            1024px, which is an iPad in landscape.

            Measured before changing it: the row already contains a 44px element
            (the locale switch carries `min-h-11` for exactly this reason), so the
            shell's 86px height is set by that and the CTA growing to 44px does not
            move it. Verified — header height is 86px before and after.

            It also reads better. A 36px pill in an 86px shell was the timid
            member of a ladder whose other rungs are 48px (hero, access); at 44px
            the header CTA is subordinate to them without looking unfinished. */}
        <div className="hidden lg:block">
          <ButtonLink href="#access" analytics={{ target: "sandbox_access", location: "header" }}>
            {t("ctaShort")}
          </ButtonLink>
        </div>

        <MobileNav
          links={links}
          navLabel={t("mobileNavLabel")}
          ctaLabel={t("ctaShort")}
          localeSwitchLabel={otherLocale.label}
          localeSwitchLocale={otherLocale.code}
          localeSwitchAriaLabel={t("localeSwitchAction")}
          openLabel={t("menuOpen")}
          closeLabel={t("menuClose")}
        />
      </div>
    </HeaderShell>
  );
}
