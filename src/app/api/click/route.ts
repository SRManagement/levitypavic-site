import { NextRequest, NextResponse } from "next/server";
import { kv } from "@vercel/kv";

const ALLOWED_PLATFORMS = ["fanvue", "instagram", "tiktok", "snapchat"] as const;
type Platform = (typeof ALLOWED_PLATFORMS)[number];

function isPlatform(value: string): value is Platform {
  return (ALLOWED_PLATFORMS as readonly string[]).includes(value);
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const platform = body?.platform;

    if (typeof platform !== "string" || !isPlatform(platform)) {
      return NextResponse.json({ error: "Invalid platform" }, { status: 400 });
    }

    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

    // Total counter per platform (all-time)
    await kv.incr(`clicks:total:${platform}`);
    // Daily counter per platform, for a simple trend view
    await kv.incr(`clicks:daily:${platform}:${today}`);
    // Keep track of which days we have data for
    await kv.sadd("clicks:days", today);

    return NextResponse.json({ ok: true });
  } catch {
    // Never let a tracking failure break the redirect experience for a visitor
    return NextResponse.json({ ok: false }, { status: 200 });
  }
}
