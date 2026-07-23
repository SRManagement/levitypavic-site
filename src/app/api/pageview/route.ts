import { NextRequest, NextResponse } from "next/server";
import { kv } from "@vercel/kv";
import { pstDateKey, pstHourKey } from "@/lib/pst";

export async function POST(req: NextRequest) {
  try {
    const now = new Date();
    const day = pstDateKey(now);
    const hour = pstHourKey(now);

    // Vercel injects this header automatically on every request served
    // through its network — no third-party geolocation service needed,
    // and it works the same whether this route runs on Edge or Node.
    const country = req.headers.get("x-vercel-ip-country") || "XX";

    await Promise.all([
      kv.incr("views:total"),
      kv.incr(`views:daily:${day}`),
      kv.incr(`views:hourly:${hour}`),
      kv.incr(`views:country:total:${country}`),
      kv.incr(`views:country:daily:${country}:${day}`),
      kv.sadd("countries:seen", country),
    ]);

    return NextResponse.json({ ok: true });
  } catch {
    // Never let a tracking failure break the visitor's experience
    return NextResponse.json({ ok: false }, { status: 200 });
  }
}
