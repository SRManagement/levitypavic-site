"use client";

import { useState } from "react";

type Range = "24h" | "48h" | "7d" | "30d" | "90d" | "custom";

type SeriesPoint = { label: string; views: number; clicks: number };
type LinkPerf = { platform: string; label: string; url: string; clicks: number };
type Country = { code: string; name: string; count: number; percent: number };

type StatsResponse = {
  totals: { views: number; clicks: number; ctr: number; activeLinks: number };
  series: SeriesPoint[];
  linksPerformance: LinkPerf[];
  topCountries: Country[];
};

const RANGE_LABELS: Record<Range, string> = {
  "24h": "24 Hours",
  "48h": "48 Hours",
  "7d": "7 Days",
  "30d": "30 Days",
  "90d": "90 Days",
  custom: "Custom",
};

export default function StatsPage() {
  const [key, setKey] = useState("");
  const [authed, setAuthed] = useState(false);
  const [data, setData] = useState<StatsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState<Range>("7d");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  async function load(selectedRange: Range = range) {
    if (!key) return;
    if (selectedRange === "custom" && (!customStart || !customEnd)) return;

    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ key, range: selectedRange });
      if (selectedRange === "custom") {
        params.set("start", customStart);
        params.set("end", customEnd);
      }
      const res = await fetch(`/api/stats?${params.toString()}`);
      if (!res.ok) throw new Error("Wrong password, or stats aren't set up yet.");
      setData(await res.json());
      setAuthed(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  function selectRange(r: Range) {
    setRange(r);
    if (r !== "custom") load(r);
  }

  if (!authed) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 bg-bg px-6 text-cream">
        <h1 className="font-display text-2xl font-bold uppercase text-cream">
          Analytics
        </h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
          className="flex gap-2"
        >
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="stats password"
            autoFocus
            className="flex-1 border border-white/15 bg-black px-3 py-2 text-sm text-cream outline-none"
          />
          <button
            type="submit"
            disabled={loading || !key}
            className="bg-red px-4 py-2 text-sm font-bold uppercase tracking-widest text-cream disabled:opacity-50"
          >
            {loading ? "..." : "View"}
          </button>
        </form>
        {error && <p className="text-sm text-red">{error}</p>}
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 bg-bg px-5 py-10 text-cream">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold uppercase text-cream">
          Analytics
        </h1>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Times shown in PST
        </p>
      </div>

      {/* Range selector */}
      <div className="flex flex-wrap gap-2">
        {(["24h", "48h", "7d", "30d", "90d", "custom"] as Range[]).map((r) => (
          <button
            key={r}
            onClick={() => selectRange(r)}
            className={`font-mono border px-3 py-1.5 text-[11px] uppercase tracking-widest transition-colors ${
              range === r
                ? "border-red bg-red text-cream"
                : "border-white/15 text-muted"
            }`}
          >
            {RANGE_LABELS[r]}
          </button>
        ))}
      </div>

      {range === "custom" && (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Start
            </span>
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="border border-white/15 bg-black px-3 py-1.5 text-sm text-cream outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              End
            </span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="border border-white/15 bg-black px-3 py-1.5 text-sm text-cream outline-none"
            />
          </label>
          <button
            onClick={() => load("custom")}
            disabled={!customStart || !customEnd || loading}
            className="bg-red px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-cream disabled:opacity-50"
          >
            Apply
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red">{error}</p>}

      {loading && !data && (
        <p className="font-mono text-xs text-muted">loading...</p>
      )}

      {data && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total Views" value={data.totals.views.toLocaleString()} />
            <StatCard label="Total Clicks" value={data.totals.clicks.toLocaleString()} />
            <StatCard
              label="Click Rate (CTR)"
              value={`${data.totals.ctr.toFixed(1)}%`}
            />
            <StatCard label="Active Links" value={String(data.totals.activeLinks)} />
          </div>

          {/* Activity chart */}
          <div className="border border-white/15 p-4">
            <div className="mb-4 flex items-center justify-between">
              <p className="font-display text-sm font-bold uppercase text-cream">
                Activity
              </p>
              <div className="flex items-center gap-4 font-mono text-[10px] uppercase tracking-widest text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 bg-white/30" /> Views
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 bg-red" /> Clicks
                </span>
              </div>
            </div>
            <ActivityChart series={data.series} />
          </div>

          {/* Links performance */}
          <div className="border border-white/15 p-4">
            <p className="font-display mb-3 text-sm font-bold uppercase text-cream">
              Links Performance
            </p>
            <div className="flex flex-col divide-y divide-white/10">
              {data.linksPerformance.map((link) => (
                <div
                  key={link.platform}
                  className="flex items-center justify-between py-3"
                >
                  <div>
                    <p className="font-mono text-xs uppercase tracking-wide text-cream">
                      {link.label}
                    </p>
                    <p className="font-mono text-[10px] text-muted">{link.url}</p>
                  </div>
                  <p className="font-display text-lg font-bold text-cream">
                    {link.clicks.toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Top countries */}
          <div className="border border-white/15 p-4">
            <p className="font-display mb-3 text-sm font-bold uppercase text-cream">
              Top Countries
            </p>
            {data.topCountries.length === 0 ? (
              <p className="font-mono text-xs text-muted">No data yet.</p>
            ) : (
              <div className="flex flex-col gap-3">
                {data.topCountries.map((c, i) => (
                  <div key={c.code}>
                    <div className="mb-1 flex items-center justify-between">
                      <p className="font-mono text-xs text-cream">
                        <span className="text-muted">#{i + 1}</span> {c.name}
                      </p>
                      <p className="font-mono text-xs text-muted">
                        {c.percent.toFixed(1)}% ({c.count.toLocaleString()})
                      </p>
                    </div>
                    <div className="h-1 w-full bg-white/10">
                      <div
                        className="h-1 bg-red"
                        style={{ width: `${c.percent}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/15 p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </p>
      <p className="font-display mt-1 text-2xl font-bold text-cream">{value}</p>
    </div>
  );
}

function ActivityChart({ series }: { series: SeriesPoint[] }) {
  const max = Math.max(1, ...series.map((p) => Math.max(p.views, p.clicks)));
  // Thin out labels if there are too many points to show cleanly
  const labelEvery = Math.ceil(series.length / 8);

  return (
    <div className="flex h-40 items-end gap-1">
      {series.map((p, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div className="flex h-32 w-full items-end justify-center gap-[2px]">
            <div
              className="w-1/2 bg-white/30"
              style={{ height: `${(p.views / max) * 100}%` }}
              title={`${p.label}: ${p.views} views`}
            />
            <div
              className="w-1/2 bg-red"
              style={{ height: `${(p.clicks / max) * 100}%` }}
              title={`${p.label}: ${p.clicks} clicks`}
            />
          </div>
          <p className="font-mono text-[9px] text-muted">
            {i % labelEvery === 0 ? p.label : ""}
          </p>
        </div>
      ))}
    </div>
  );
}
