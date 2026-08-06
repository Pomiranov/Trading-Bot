import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "ru"],
  defaultLocale: "en",
  localePrefix: "always",
  // The site ships HSTS with preload, so the locale cookie should never travel
  // over plain HTTP either. Locale is not sensitive; this is hygiene, not a
  // secret — dev on http://localhost is unaffected because browsers treat
  // localhost as a secure context for Secure cookies.
  localeCookie: { secure: true },
});

export type Locale = (typeof routing.locales)[number];
