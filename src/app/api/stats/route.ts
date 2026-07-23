import { NextRequest, NextResponse } from "next/server";
import { kv } from "@vercel/kv";
import { pstDateKey, pstHourKey, pstDateLabel, pstHourLabel } from "@/lib/pst";

const PLATFORMS = ["fanvue", "instagram", "tiktok", "snapchat", "telegram"] as const;

const PLATFORM_META: Record<(typeof PLATFORMS)[number], { label: string; url: string }> = {
  fanvue: { label: "Exclusive Content", url: "fanvue.com/sparedbytheking" },
  telegram: { label: "Telegram", url: "t.me/..." },
  instagram: { label: "Instagram", url: "instagram.com/SPAREDBYTHEKING" },
  snapchat: { label: "Snapchat", url: "snapchat.com/add/levitypavic" },
  tiktok: { label: "TikTok", url: "tiktok.com/@sparedbytheking" },
};

type Range = "24h" | "48h" | "7d" | "30d" | "90d" | "custom";

function countryName(code: string): string {
  if (code === "XX") return "Unknown";
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(code) || code;
  } catch {
    return code;
  }
}

export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key");
  if (!process.env.STATS_PASSWORD || key !== process.env.STATS_PASSWORD) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const range = (req.nextUrl.searchParams.get("range") as Range) || "7d";
  const now = new Date();

  // Build the list of bucket keys (and their display labels) for the
  // requested range. 24h/48h use hourly granularity; everything else
  // uses daily — an hourly chart spanning 90 days would be unreadable
  // and enormous to fetch, so daily is the right grain there.
  const bucketKeys: string[] = [];
  const bucketLabels: string[] = [];
  let granularity: "hour" | "day" = "day";

  if (range === "24h" || range === "48h") {
    granularity = "hour";
    const hours = range === "24h" ? 24 : 48;
    for (let i = hours - 1; i >= 0; i--) {
      const t = new Date(now.getTime() - i * 60 * 60 * 1000);
      const hk = pstHourKey(t);
      bucketKeys.push(hk);
      bucketLabels.push(pstHourLabel(hk));
    }
  } else {
    granularity = "day";
    let days = 7;
    let startOverride: Date | null = null;
    let endOverride: Date | null = null;

    if (range === "30d") days = 30;
    else if (range === "90d") days = 90;
    else if (range === "custom") {
      const startParam = req.nextUrl.searchParams.get("start");
      const endParam = req.nextUrl.searchParams.get("end");
      if (startParam && endParam) {
        startOverride = new Date(`${startParam}T12:00:00Z`);
        endOverride = new Date(`${endParam}T12:00:00Z`);
      }
    }

    if (startOverride && endOverride) {
      const msPerDay = 24 * 60 * 60 * 1000;
      const spanDays = Math.max(
        1,
        Math.min(
          366,
          Math.round((endOverride.getTime() - startOverride.getTime()) / msPerDay) + 1
        )
      );
      for (let i = 0; i < spanDays; i++) {
        const t = new Date(startOverride.getTime() + i * msPerDay);
        const dk = pstDateKey(t);
        bucketKeys.push(dk);
        bucketLabels.push(pstDateLabel(dk));
      }
    } else {
      for (let i = days - 1; i >= 0; i--) {
        const t = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
        const dk = pstDateKey(t);
        bucketKeys.push(dk);
        bucketLabels.push(pstDateLabel(dk));
      }
    }
  }

  const viewKeys = bucketKeys.map(
    (k) => `views:${granularity === "hour" ? "hourly" : "daily"}:${k}`
  );
  const clickKeys = bucketKeys.map(
    (k) => `clicks:${granularity === "hour" ? "hourly" : "daily"}:all:${k}`
  );

  const [viewCounts, clickCounts] = await Promise.all([
    kv.mget<(number | null)[]>(...viewKeys),
    kv.mget<(number | null)[]>(...clickKeys),
  ]);

  const series = bucketLabels.map((label, i) => ({
    label,
    views: viewCounts[i] ?? 0,
    clicks: clickCounts[i] ?? 0,
  }));

  const totalViews = series.reduce((sum, p) => sum + p.views, 0);
  const totalClicks = series.reduce((sum, p) => sum + p.clicks, 0);
  const ctr = totalViews > 0 ? (totalClicks / totalViews) * 100 : 0;

  // Links performance — all-time totals per platform, not range-scoped
  // (a running leaderboard, not a per-window breakdown).
  const platformTotals = await kv.mget<(number | null)[]>(
    ...PLATFORMS.map((p) => `clicks:total:${p}`)
  );
  const linksPerformance = PLATFORMS.map((platform, i) => ({
    platform,
    label: PLATFORM_META[platform].label,
    url: PLATFORM_META[platform].url,
    clicks: platformTotals[i] ?? 0,
  })).sort((a, b) => b.clicks - a.clicks);

  // Top countries — all-time totals, not range-scoped.
  const seenCountries = (await kv.smembers("countries:seen")) ?? [];
  const countryTotals =
    seenCountries.length > 0
      ? await kv.mget<(number | null)[]>(
          ...seenCountries.map((c) => `views:country:total:${c}`)
        )
      : [];
  const totalCountryViews = countryTotals.reduce((sum: number, c) => sum + (c ?? 0), 0);
  const topCountries = seenCountries
    .map((code, i) => ({
      code,
      name: countryName(code),
      count: countryTotals[i] ?? 0,
      percent:
        totalCountryViews > 0 ? ((countryTotals[i] ?? 0) / totalCountryViews) * 100 : 0,
    }))
    .filter((c) => c.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  return NextResponse.json({
    totals: {
      views: totalViews,
      clicks: totalClicks,
      ctr,
      activeLinks: PLATFORMS.length,
    },
    series,
    linksPerformance,
    topCountries,
  });
}
