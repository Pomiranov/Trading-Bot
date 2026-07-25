import { NextResponse } from "next/server";
import { betaSignupSchema } from "@/lib/beta/schema";
import { getBetaAdapter } from "@/lib/beta/adapter";

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);
  const parsed = betaSignupSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json({ ok: false, error: "invalid" }, { status: 400 });
  }

  if (parsed.data.company) {
    return NextResponse.json({ ok: true });
  }

  await getBetaAdapter().submit({ email: parsed.data.email });

  return NextResponse.json({ ok: true });
}
