import { NextRequest, NextResponse } from "next/server";
import { kv } from "@vercel/kv";
import { pstDateKey, pstHourKey } from "@/lib/pst";

const ALLOWED_PLATFORMS = [
  "fanvue",
  "instagram",
  "tiktok",
  "snapchat",
  "telegram",
] as const;
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

    const now = new Date();
    const day = pstDateKey(now);
    const hour = pstHourKey(now);

    await Promise.all([
      // Per-platform counters
      kv.incr(`clicks:total:${platform}`),
      kv.incr(`clicks:daily:${platform}:${day}`),
      kv.incr(`clicks:hourly:${platform}:${hour}`),
      // Combined-across-all-platforms counters, kept in parallel so the
      // stats dashboard doesn't need to sum every platform at read time
      kv.incr(`clicks:total:all`),
      kv.incr(`clicks:daily:all:${day}`),
      kv.incr(`clicks:hourly:all:${hour}`),
    ]);

    return NextResponse.json({ ok: true });
  } catch {
    // Never let a tracking failure break the redirect experience for a visitor
    return NextResponse.json({ ok: false }, { status: 200 });
  }
}
