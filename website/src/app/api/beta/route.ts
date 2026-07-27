import { NextResponse } from "next/server";
import { betaSignupSchema } from "@/lib/beta/schema";
import { getBetaAdapter } from "@/lib/beta/adapter";

export async function POST(request: Request) {
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
