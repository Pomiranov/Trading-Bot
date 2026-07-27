import type { Metadata } from "next";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import {
  getMessages,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { notFound } from "next/navigation";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { routing } from "@/lib/i18n/routing";
import { fontVariables } from "@/lib/fonts";
import { LenisProvider } from "@/components/motion/lenis-provider";
import { PostHogProvider } from "@/lib/analytics/posthog-provider";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

/**
 * Only `en` and `ru` may ever match this segment.
 *
 * ── The 500s this fixes ──
 *
 * `[locale]` is a root-level dynamic segment, so with the default
 * `dynamicParams: true` it matched *every* single-segment path — including the
 * root metadata routes. `/robots.txt`, `/sitemap.xml` and `/icon.svg` were all
 * being rendered as the homepage with `locale = "robots.txt"`, which then blew
 * up three levels down:
 *
 *   ENOENT: scandir '…/content/robots.txt/engine-pipeline'
 *   ENOENT: open    '…/content/robots.txt/strategies.json'
 *   RangeError: Incorrect locale information provided   (new Intl.DateTimeFormat)
 *
 * All three returned **500 in both dev and production**, verified against
 * `next start`. For a marketing site that means robots.txt and sitemap.xml —
 * the two files every crawler asks for first — were hard errors.
 *
 * The `hasLocale` guard below could not prevent this: a layout and its page
 * render concurrently, so `page.tsx` had already begun fetching content with
 * the bogus locale before `notFound()` was reached. The guard turns a bad
 * locale into a 404 *after* the damage; `dynamicParams = false` stops the route
 * from matching at all, which is what lets the real metadata routes resolve.
 *
 * Next's own `isStaticMetadataRoute` deliberately treats `robots.txt` and
 * `sitemap.xml` as dynamic entrypoints, so they cannot win this contest on
 * their own — the dynamic segment has to stop competing.
 *
 * The guard below stays as defence in depth for the typed-params contract.
 */
export const dynamicParams = false;

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quantflow.app";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "seo" });

  const title = t("title");
  const description = t("description");

  return {
    metadataBase: new URL(SITE_URL),
    title,
    description,
    alternates: {
      canonical: `/${locale}`,
      languages: {
        en: "/en",
        ru: "/ru",
      },
    },
    openGraph: {
      type: "website",
      url: `/${locale}`,
      title,
      description,
      siteName: "QuantFlow",
      locale: locale === "ru" ? "ru_RU" : "en_US",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} className={fontVariables} suppressHydrationWarning>
      <body className="antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <PostHogProvider>
            <LenisProvider>{children}</LenisProvider>
          </PostHogProvider>
        </NextIntlClientProvider>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
