"use client";

import { useState } from "react";

type StatsResponse = {
  totals: Record<string, number>;
  daily: Record<string, Record<string, number>>;
};

export default function StatsPage() {
  const [key, setKey] = useState("");
  const [data, setData] = useState<StatsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/stats?key=${encodeURIComponent(key)}`);
      if (!res.ok) throw new Error("Wrong password, or stats aren't set up yet.");
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-6 bg-bg px-6 py-16 text-cream">
      <h1 className="font-display text-2xl italic">Link clicks</h1>

      <div className="flex gap-2">
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="stats password"
          className="flex-1 rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm outline-none"
        />
        <button
          onClick={load}
          disabled={loading || !key}
          className="rounded-lg px-4 py-2 text-sm font-medium text-bg disabled:opacity-50"
          style={{ background: "linear-gradient(135deg, var(--rose), var(--gold))" }}
        >
          {loading ? "Loading…" : "View"}
        </button>
      </div>

      {error && <p className="text-sm text-rose">{error}</p>}

      {data && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(data.totals).map(([platform, count]) => (
              <div key={platform} className="rounded-xl bg-surface p-4">
                <p className="text-xs capitalize text-muted">{platform}</p>
                <p className="mt-1 text-2xl">{count}</p>
              </div>
            ))}
          </div>

          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-muted">
              Last 14 days
            </p>
            <div className="flex flex-col gap-1 text-sm">
              {Object.entries(data.daily)
                .sort((a, b) => (a[0] < b[0] ? 1 : -1))
                .map(([day, counts]) => (
                  <div
                    key={day}
                    className="flex items-center justify-between border-b border-white/5 py-1.5"
                  >
                    <span className="text-muted">{day}</span>
                    <span>
                      {Object.entries(counts)
                        .map(([p, c]) => `${p}: ${c}`)
                        .join("  ·  ")}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
