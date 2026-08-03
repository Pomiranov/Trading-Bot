import { execSync } from "node:child_process";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/lib/i18n/request.ts");

function resolveBuildSha(): string {
  if (process.env.VERCEL_GIT_COMMIT_SHA) {
    return process.env.VERCEL_GIT_COMMIT_SHA.slice(0, 7);
  }
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "dev";
  }
}

const nextConfig: NextConfig = {
  /**
   * ── Do not add `distDir` here ──
   *
   * Tried, measured, reverted. The motivation was real: `next build` and
   * `next dev --turbopack` share `.next`, so verifying a production build while
   * a dev server is running corrupts it, and a `NEXT_DIST_DIR` override looked
   * like the safe way out.
   *
   * It is not. With any non-default `distDir`, Turbopack fails to resolve its
   * own virtual font module for `next/font/google` —
   *
   *     Module not found: Can't resolve
   *     '@vercel/turbopack-next/internal/font/google/font'
   *
   * — on every `@font-face` block of both families, and the build dies.
   * Verified both ways on 15.5.22: identical source builds clean at the default
   * path and fails at `.next-verify`.
   *
   * To build without disturbing a running dev server, copy the project instead
   * (`rsync` the source, `cp -Rc` node_modules for an APFS clone) and build the
   * copy at the default path.
   */
  typedRoutes: true,
  /**
   * ── Why this is set, and it is not a cosmetic preference ──
   *
   * Next's dev-tools indicator defaults to the bottom-left corner and renders as
   * a ~32px circular button with the Next logo in it. That is the same corner and
   * the same shape as the assistant orb (`components/assistant/*`), and it was
   * read as site furniture during review — "the round button with an N in it" —
   * which cost a full audit pass to establish was Next's own overlay and not a
   * component of this page at all.
   *
   * It does not ship: `devIndicators` has no effect on a production build, and
   * nothing in the corner of a deployed page comes from here. Moving it to the
   * opposite corner in dev is what stops the two being confused again.
   */
  devIndicators: { position: "bottom-right" },
  /* `X-Powered-By: Next.js` on every response. Not a vulnerability, but it
     hands a scanner the framework for free and buys nothing in return. */
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_BUILD_SHA: resolveBuildSha(),
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
  },
  async headers() {
    return [
      /**
       * Baseline security headers for every route.
       *
       * Deliberately the set that cannot break a static marketing page. Each one
       * closes a real class of attack and none of them depends on knowing what
       * the page renders:
       *
       *   • nosniff              — stops a response being re-interpreted as a
       *                            script because a browser guessed its type
       *   • frame-ancestors      — clickjacking. The modern form of
       *                            X-Frame-Options; a CSP carrying *only* this
       *                            directive constrains framing and nothing
       *                            else, so it cannot break inline styles,
       *                            Next's bootstrap scripts, PostHog or Vercel
       *                            Analytics. X-Frame-Options is sent alongside
       *                            it for browsers that predate the directive.
       *   • Referrer-Policy      — a full URL is never sent cross-origin; the
       *                            origin alone goes to HTTPS destinations
       *   • Permissions-Policy   — the page uses no device APIs, so every one
       *                            of them is denied outright. This is also the
       *                            header the pricing copy's provenance note
       *                            refers to: `payment=()` is the only match for
       *                            "payment" anywhere in this repository, which
       *                            is how we know there is no billing code.
       *   • HSTS                 — the site is served over HTTPS only
       *   • COOP                 — severs the opener relationship with any
       *                            window that navigated to us
       *
       * ── What is deliberately NOT here ──
       *
       * A full Content-Security-Policy with script-src. Next.js injects inline
       * bootstrap scripts, so a real policy needs per-request nonces from
       * middleware, and `next-intl`'s middleware currently owns that file. That
       * is a change with a live failure mode — a wrong nonce is a blank page —
       * and it belongs in its own pass with its own verification rather than
       * riding along with a visual one. Recorded in docs/SECURITY_REVIEW.md.
       */
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value:
              "accelerometer=(), autoplay=(self), camera=(), display-capture=(), encrypted-media=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), usb=(), interest-cohort=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
        ],
      },
      {
        // Hero media is large and never mutated in place — new assets ship
        // under new, version-suffixed filenames (see docs/VIDEO_ASSET_GUIDE.md
        // §7). Without this, Vercel serves /public as `max-age=0,
        // must-revalidate`, which revalidates the video on every navigation.
        source: "/media/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
