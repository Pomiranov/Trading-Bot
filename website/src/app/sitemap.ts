import type { MetadataRoute } from "next";
import { routing } from "@/lib/i18n/routing";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quantflow.example";

export default function sitemap(): MetadataRoute.Sitemap {
  return routing.locales.map((locale) => ({
    url: `${SITE_URL}/${locale}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    alternates: {
      languages: Object.fromEntries(
        routing.locales.map((l) => [l, `${SITE_URL}/${l}`]),
      ),
    },
  }));
}
