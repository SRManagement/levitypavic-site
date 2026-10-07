import { NextRequest, NextResponse } from "next/server";

// Checks a Cloudflare Turnstile token with Cloudflare's servers. The secret
// key lives only here on the server (Vercel environment variable
// TURNSTILE_SECRET_KEY) and is never sent to the visitor's browser.
export async function POST(req: NextRequest) {
  const secret = process.env.TURNSTILE_SECRET_KEY;

  // No key set up yet: let everyone through rather than locking out real
  // visitors because of a missing setting.
  if (!secret) {
    return NextResponse.json({ success: true });
  }

  let token = "";
  try {
    const body = await req.json();
    token = typeof body?.token === "string" ? body.token : "";
  } catch {
    // fall through with an empty token
  }

  if (!token) {
    return NextResponse.json({ success: false }, { status: 400 });
  }

  const ip =
    req.headers.get("x-real-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    undefined;

  try {
    const res = await fetch(
      "https://challenges.cloudflare.com/turnstile/v0/siteverify",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret, response: token, remoteip: ip }),
      }
    );
    const data = (await res.json()) as { success?: boolean };
    return NextResponse.json({ success: data.success === true });
  } catch {
    // Cloudflare itself unreachable: don't punish real visitors for an
    // outage on Cloudflare's side.
    return NextResponse.json({ success: true });
  }
}
