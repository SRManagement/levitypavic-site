import { NextRequest, NextResponse } from "next/server";
import { kv } from "@vercel/kv";

const PLATFORMS = ["fanvue", "instagram", "tiktok", "snapchat"] as const;

export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key");

  if (!process.env.STATS_PASSWORD || key !== process.env.STATS_PASSWORD) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const totals: Record<string, number> = {};
  for (const platform of PLATFORMS) {
    totals[platform] = (await kv.get<number>(`clicks:total:${platform}`)) ?? 0;
  }

  const days = ((await kv.smembers("clicks:days")) ?? []).sort().slice(-14);
  const daily: Record<string, Record<string, number>> = {};
  for (const day of days) {
    daily[day] = {};
    for (const platform of PLATFORMS) {
      daily[day][platform] =
        (await kv.get<number>(`clicks:daily:${platform}:${day}`)) ?? 0;
    }
  }

  return NextResponse.json({ totals, daily });
}
