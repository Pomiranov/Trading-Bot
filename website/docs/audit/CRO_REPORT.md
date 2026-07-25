# CRO_REPORT.md

**Scope:** the actual, single conversion mechanism on the site — the beta-access email form — plus everything that feeds or blocks it.

## 1. There is exactly one conversion path, reachable only after a full scroll

`page.tsx` renders one form (`BetaForm`, inside `CtaSection`, the 7th of 8 sections) and one secondary link (`ExploreLink`, which scrolls back *up* to the hero — not a conversion action). There is no header/nav, so the `nav.requestAccess` copy that exists in both locale files (`messages/en.json:8`, `messages/ru.json:8`) is never rendered anywhere.

This means: a visitor convinced by the Hero, or by the Philosophy section, has zero way to act on that conviction without scrolling through the Engine Pipeline (a pinned, scroll-jacked animation on desktop), the Learning System, the Dashboard Preview, and the Strategy Table first.

| Issue | Business impact | User impact | Solution | Expected benefit | Priority |
|---|---|---|---|---|---|
| Single CTA, unreachable without a full-page scroll; translated nav CTA copy exists but is unused | Every unit of early-conversion intent decays across ~5 more sections and at least one animation-heavy scroll-jack before the visitor reaches a way to act | High-intent visitors have no fast path; low-intent visitors who do reach the bottom have had 5 more chances to lose interest or get distracted | Add a minimal persistent header exposing `nav.requestAccess`, smooth-scrolling to `#cta-heading` (id already exists) | Directly shortens the path-to-conversion for the highest-intent segment without adding any new copy or changing the page's pacing for everyone else | Critical |

## 2. The form itself: what happens after "Request access"

Read directly from `beta-form.tsx`, `schema.ts`, `adapter.ts`, `api/beta/route.ts`:

- **Fields:** email (visible) + a honeypot `company` field (hidden, for bots). No name, no company/fund name, no "what are you looking for" — minimal friction, which is correct for this stage.
- **Destination:** the only adapter implemented is `consoleAdapter` — a submitted email is `console.log`'d server-side and nothing else happens. No CRM, no spreadsheet, no email service is wired up despite `BETA_ADAPTER=console` in `.env.example` implying a swappable adapter pattern exists for a reason.
- **Confirmation:** none. No confirmation email is sent to the submitter. The on-page message ("Request received. We follow up if it's a fit.") is the only acknowledgment they ever get.
- **Rate limiting / abuse protection:** honeypot only. No IP throttling, no CAPTCHA, no per-email dedup check on the server.
- **Error handling:** a client-validation error (malformed email) and a server/network failure render the *identical* string ("Enter a valid email address.") — see `beta-form.tsx:96-105`. A visitor who typed a valid email but hit a transient server error is told their email is wrong, and has no way to know otherwise.

| Issue | Business impact | User impact | Solution | Expected benefit | Priority |
|---|---|---|---|---|---|
| Submissions only reach a server console log — no durable destination | Every real signup today is one server restart away from being permanently lost; there is currently no list of who asked for access | None visible to the user (the UI lies gently — "we follow up" implies a process that doesn't yet exist) | Wire a real adapter (Resend to a team inbox, or a lightweight table/sheet) behind the existing `BETA_ADAPTER` env switch | Turns the site's entire purpose (collecting qualified leads) into something that actually works | Critical |
| No confirmation email sent | Visitors have no artifact confirming their request was received beyond a page state that disappears on refresh/navigation | Lower trust that "we follow up" is real; no way to reference their own submission later | Send a short confirmation email once a real adapter exists (bundle with the fix above) | Reinforces the "we follow up if it's a fit" promise with actual proof | High |
| Identical error copy for invalid-input vs. server-failure | Support/trust cost — a valid submission that failed server-side looks, from the user's side, like their own mistake, and retrying with the same email will fail again silently | Misleading; the fix (re-enter a "valid" email) doesn't address the actual (server-side) problem | Add a distinct network/server-error message and branch `beta-form.tsx`'s two failure paths on it | Removes a real dead-end from the only conversion flow that exists | High |
| No rate limiting on `/api/beta` | A scripted flood of POSTs (even without malicious intent — e.g. a broken retry loop) has no server-side backstop beyond the honeypot | None directly, but a flooded console-log adapter is a symptom of a flow that was never load-considered | Add basic per-IP throttling once a real (non-console) adapter is chosen — the right mechanism depends on where this deploys (Vercel Edge vs. Node), so this is a decision, not a drop-in patch | Protects the eventual real destination (inbox/CRM) from spam once the console adapter is replaced | Medium |

## 3. Hero → CTA: what's between them

Per `UX_REVIEW.md`'s section notes: Philosophy (low friction, well-executed) → Engine Pipeline (scroll-jacked pin on desktop) → Learning System (interactive, engaging) → Dashboard Preview (static) → Strategy Table (static) → CTA. None of these sections repeat or reinforce the CTA — the ask appears exactly once, cold, after all the proof has already been shown. This is a defensible pattern for an exclusive/manifesto positioning (see `BRAND_POSITIONING.md`) but it does mean the site currently has zero redundancy in its conversion mechanism: if a visitor closes the tab mid-scroll, there was never a second chance to convert.

| Issue | Business impact | User impact | Solution | Expected benefit | Priority |
|---|---|---|---|---|---|
| Zero redundancy in the CTA — it exists in exactly one place | Any visitor who doesn't complete the full scroll has had no opportunity to convert at all | N/A (this is a business-side loss, not a user-facing complaint) | The header fix in §1 is the primary redundancy; a secondary, lighter-weight repeat (e.g., after the Strategy Table, which is the strongest trust moment on the page) could reinforce it further | Captures conversions from visitors who stop scrolling right after the single most convincing section | Medium |

## 4. Footer as a conversion/trust dead end

Covered in depth in `MARKETING_AUDIT.md` §3 — flagged here specifically for its CRO impact: a visitor who scrolls all the way to the footer (i.e., a highly engaged visitor who read the whole page and *didn't* convert on the CTA above it) is the single highest-value remaining segment on the page, and every link available to them (`Manifesto`, `System`, `Research`, `Contact`) is a no-op. This is the second-highest-value moment on the page after the Hero, currently wasted.

## 5. Analytics: what's measurable today, and the one gap

`src/lib/analytics/events.ts` defines a clean, privacy-conscious event set (`cta_clicked`, `beta_submitted` with `result: success|error|invalid`, `scroll_depth` at 25/50/75/100%, `scene_interaction`, `journey_step` per section). This is materially better instrumentation than most sites at this stage ship with, and it already answers the two most important CRO questions once there's real traffic: *where do people drop off* (`scroll_depth` + `journey_step`) and *does the form work* (`beta_submitted` by result). `track()` correctly no-ops without a PostHog key configured, so nothing is silently broken in dev/preview.

**Gap:** there is no event for the (currently nonexistent) header CTA or footer link clicks, because those elements don't exist yet. Once §1's header ships, its click should fire `cta_clicked` with a new `location: "nav"` value (the type already supports arbitrary `location: string`) so its contribution can be measured against the existing bottom-of-page CTA.

## Priority Summary

- **Critical:** persistent header CTA (§1); real signup destination behind the adapter (§2).
- **High:** confirmation email; distinct error messaging (§2); dead footer links (cross-ref `MARKETING_AUDIT.md`).
- **Medium:** rate limiting once a real adapter exists; secondary CTA repetition after the Strategy Table.
