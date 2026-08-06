import { NextResponse } from "next/server";
import { betaSignupSchema } from "@/lib/beta/schema";
import { getBetaAdapter } from "@/lib/beta/adapter";

/**
 * Minimal in-memory per-IP limiter — the open item B in docs/SECURITY_REVIEW.md.
 *
 * This endpoint is unauthenticated and, under BETA_ADAPTER=webhook, every call
 * produces an outbound fetch; without a floor one curl loop floods the signup
 * list. A fixed window of 5 requests per minute per IP is far above any human
 * rate on a single email form and needs no new dependency.
 *
 * Honest about its limits: the Map is per-process (resets on redeploy, not
 * shared across serverless instances) and X-Forwarded-For is spoofable by a
 * determined attacker. It is a floor, not a WAF — platform-level rate limiting
 * remains the real control on a production deployment. The success/validation
 * contract for normal clients is unchanged; only floods see 429.
 */
const WINDOW_MS = 60_000;
const WINDOW_LIMIT = 5;
const hits = new Map<string, { count: number; windowStart: number }>();

function limited(ip: string, now: number): boolean {
  // Opportunistic sweep so an abandoned flood cannot grow the Map forever.
  if (hits.size > 10_000) {
    for (const [k, v] of hits) if (now - v.windowStart > WINDOW_MS) hits.delete(k);
  }
  const entry = hits.get(ip);
  if (!entry || now - entry.windowStart > WINDOW_MS) {
    hits.set(ip, { count: 1, windowStart: now });
    return false;
  }
  entry.count += 1;
  return entry.count > WINDOW_LIMIT;
}

export async function POST(request: Request) {
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  if (limited(ip, Date.now())) {
    return NextResponse.json({ ok: false, error: "rate_limited" }, { status: 429 });
  }

  const body: unknown = await request.json().catch(() => null);
  const parsed = betaSignupSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json({ ok: false, error: "invalid" }, { status: 400 });
  }

  // Honeypot hit: answer exactly like a success so the bot learns nothing.
  // Claiming delivery here is safe — no human is reading this response.
  if (parsed.data.company) {
    return NextResponse.json({ ok: true, delivered: true });
  }

  const { delivered } = await getBetaAdapter().submit({ email: parsed.data.email });

  // `delivered` is passed through so the UI can only promise a follow-up when
  // the address actually reached a destination. See lib/beta/adapter.ts.
  return NextResponse.json({ ok: true, delivered });
}
