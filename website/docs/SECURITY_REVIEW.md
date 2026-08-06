# Website security review

**Scope:** `website/` only — the Next.js marketing site. Backend, trading-core,
bot, broker and DB code were explicitly out of scope for this pass and were not
read for defects or modified. Nothing in this document is a finding about them.

**Date:** 2026-07-28
**Reviewed at:** commit on `quant-site-approved-reference-redesign`

---

## Summary

| Area | Result |
|---|---|
| Secrets / keys in client code | None found |
| `dangerouslySetInnerHTML` | Zero occurrences |
| Third-party scripts | Three, all first-party npm packages, all opt-in |
| Console leaks | Server-side only; none in client bundles |
| Form validation | Shared zod schema, client and server, plus a honeypot |
| Outbound links | None on the page — nothing needs `rel` |
| Security headers | **Were absent. Added in this pass.** |
| Dependency advisories | **8 high-severity Next.js advisories closed in this pass.** 6 remain, all upstream-blocked |
| Backend detail on the landing page | Source references only; no hosts, credentials or deployment caveats |

---

## Fixed in this pass

### 1. No security headers were being sent (now added)

`next.config.ts` previously configured one header — a `Cache-Control` for
`/media/*`. Every response therefore went out with no `X-Content-Type-Options`,
no framing protection, no `Referrer-Policy`, no `Permissions-Policy` and no
HSTS.

Added for `/:path*`:

| Header | Value | Closes |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | MIME-confusion execution |
| `Content-Security-Policy` | `frame-ancestors 'none'` | Clickjacking |
| `X-Frame-Options` | `DENY` | Clickjacking, pre-CSP browsers |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | URL leakage to third parties |
| `Permissions-Policy` | all device APIs `()`, `autoplay=(self)` | Unintended API access |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | Protocol downgrade |
| `Cross-Origin-Opener-Policy` | `same-origin` | Cross-origin window handles |

The CSP deliberately carries **only** `frame-ancestors`. A policy with that one
directive constrains framing and nothing else, so it cannot break Next's inline
bootstrap scripts, PostHog or Vercel Analytics — see the open item below.

### 2. Next.js patched, 15.5.20 → 15.5.22

Closed eight high-severity advisories in the framework itself: DoS in App Router
Server Actions (`GHSA-m99w-x7hq-7vfj`), SSRF in Server Actions on custom servers
(`GHSA-89xv-2m56-2m9x`), two response-body cache-confusion issues
(`GHSA-68g3-v927-f742`, `GHSA-4633-3j49-mh5q`), unbounded Edge Server Action
payload (`GHSA-4c39-4ccg-62r3`), SSRF via rewrite destination hostname
(`GHSA-p9j2-gv94-2wf4`), DoS in the Image Optimization API via SVG
(`GHSA-q8wf-6r8g-63ch`), and unauthenticated disclosure of internal Server
Function endpoints (`GHSA-955p-x3mx-jcvp`).

Most are not reachable on a static marketing site — there are no Server Actions
and no custom server here — but this is a patch release inside the same minor,
so there was no reason to carry them. `eslint-config-next` was moved in step.

---

## Verified clean

**No secrets in client code.** Every `process.env` read is either
`NEXT_PUBLIC_*` (site URL, PostHog key and host, build SHA and time) or
server-only (`BETA_ADAPTER`, `BETA_WEBHOOK_URL`, read inside
`src/lib/beta/adapter.ts`, which is imported only by a route handler).
`.env.example` contains no real values. No `.env` file is present in `website/`.

**No `dangerouslySetInnerHTML` anywhere.** MDX content goes through
`next-mdx-remote`, which renders to React elements rather than to markup.

**No console leaks in the browser.** The only `console.*` calls in the codebase
are three in `src/lib/beta/adapter.ts`, all in server-only code paths. One logs a
submitted email address to the *server* console when no destination is
configured; that is deliberate and documented, but see the open item below.

**No unsafe external scripts.** Three third-party runtime integrations, all
first-party npm packages bundled by Next rather than remote `<script>` tags:
`@vercel/analytics`, `@vercel/speed-insights`, and `posthog-js`. PostHog no-ops
entirely when `NEXT_PUBLIC_POSTHOG_KEY` is unset, which is the state in dev and
preview.

**No outbound links.** Every anchor on the page is an in-page hash or a locale
switch. There is no `target="_blank"` and therefore no `rel="noopener"` gap. If
an external link is ever added it needs `rel="noopener noreferrer"`.

**Form handling is sound.** `src/lib/beta/schema.ts` is a single zod schema used
by both `AccessForm` (through `@hookform/resolvers`) and the route handler, so
the server never trusts the client's validation. The route parses with
`safeParse`, returns a flat `{ ok: false, error: "invalid" }` on failure with no
schema detail echoed back, and answers a honeypot hit with a fabricated success
so a bot learns nothing. `JSON.parse` failures are caught. The input is
`type="email"` with `aria-invalid`/`aria-describedby` wired to a visible error.

**No sensitive backend detail on the page.** The `sourceRef` values name Python
symbols and line numbers (`bot/broker/base.py:141-219`) — that is deliberate
provenance for verifiable claims and is not exploitable: it exposes no host, no
route, no credential and no version. The FAQ answers "Где хранятся API-ключи?"
in product terms without describing the storage mechanism. No deployment
caveats, internal hostnames or infrastructure names appear in the copy.

---

## Open items — not fixed here, deliberately

### A. No full Content-Security-Policy

The CSP added above covers framing only. A real `script-src`/`style-src` policy
needs per-request nonces generated in middleware, and `src/middleware.ts`
currently belongs to `next-intl`'s `createMiddleware`. Composing a nonce
generator around it is doable but has a live failure mode — a wrong or missing
nonce is a blank page, not a degraded one — so it wants its own change with its
own verification rather than riding along with a visual pass.

When it is done: `style-src` will need `'unsafe-inline'` regardless, because
Motion writes inline styles on every reveal; `connect-src` will need the PostHog
host and `/_vercel/insights`.

### B. `/api/beta` has no rate limit

The endpoint accepts unauthenticated POSTs and, when `BETA_ADAPTER=webhook`, is
an unauthenticated trigger for an outbound request per call. Today the default
adapter only logs, so the practical exposure is log volume — but the moment a
webhook destination is configured, this becomes a way to flood it.

Recommended before wiring a real destination: a per-IP limit at the edge
(Vercel WAF or `@upstash/ratelimit`), and a `maxDuration` on the route.

### C. The console adapter logs email addresses server-side

`consoleAdapter` writes the submitted address to the server log. That is the
honest behaviour — it reports `delivered: false` so the UI cannot promise a
follow-up — but it does put personal data in a log with whatever retention the
host applies. Fine for local dev; before this is deployed anywhere real, either
configure `BETA_ADAPTER=webhook` or reduce the log line to a count.

### D. Six dependency advisories remain, all upstream-blocked

| Package | Severity | Path | Why it stands |
|---|---|---|---|
| `postcss` | high | bundled inside `next` | Only `npm audit fix --force` clears it, and its proposed fix is `next@9.3.3` — a five-major downgrade. Needs an upstream Next release. Build-time only; not shipped to the client. |
| `sharp` | high | bundled inside `next` | Same. Image-optimisation path, build/server only. |
| `brace-expansion` | high | `@ts-morph/common` ← `shadcn` | Dev tooling, never executed at runtime or in a request path. |
| `@hono/node-server` | moderate | `@modelcontextprotocol/sdk` ← `shadcn` | Same. The advisory is a Windows-only path traversal in a static file server this project never starts. |

Related: **`shadcn` is in `dependencies`, not `devDependencies`.** It is a CLI —
it ships nothing to the browser — and it is what drags `@ts-morph` and the MCP
SDK into a production install. It was left where it is on purpose: `globals.css`
does `@import "shadcn/tailwind.css"`, so the package must be present at *build*
time, and moving it would break any deploy that installs with `--omit=dev`.
Worth doing, but it needs the deploy install command checked first.

---

## Re-running this review

```bash
cd website
npm audit --omit=dev
grep -rn "dangerouslySetInnerHTML" src/
grep -rn 'target="_blank"' src/            # each hit needs rel="noopener noreferrer"
grep -rn "console\." src/ --include="*.tsx" # must stay empty for client components
grep -rn "process.env" src/                 # every hit must be NEXT_PUBLIC_* or server-only
```

Headers can be confirmed against a running production server with
`curl -sI http://localhost:3000/ru`.
