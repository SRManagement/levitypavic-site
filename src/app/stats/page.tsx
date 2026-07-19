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
    if (!key) return;
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
    <main style={{ minHeight: "100vh", width: "100%", background: "#0b0b0d", color: "#f5f3f1", padding: "64px 24px", maxWidth: "480px", margin: "0 auto" }}>
      <h1 style={{ fontSize: "24px", fontWeight: 600, fontStyle: "italic", marginBottom: "24px" }}>Link clicks</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        style={{ display: "flex", flexDirection: "column", gap: "12px" }}
      >
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="stats password"
          autoFocus
          style={{
            width: "100%",
            boxSizing: "border-box",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.2)",
            background: "#17161a",
            color: "#f5f3f1",
            padding: "12px",
            fontSize: "16px",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={loading || !key}
          style={{
            width: "100%",
            borderRadius: "8px",
            padding: "14px",
            fontSize: "16px",
            fontWeight: 600,
            background: loading || !key ? "#7a3a4a" : "#ff4d79",
            color: "#0b0b0d",
            border: "none",
            cursor: loading || !key ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Loading..." : "View stats"}
        </button>
      </form>

      {error && <p style={{ color: "#ff4d79", fontSize: "14px", marginTop: "12px" }}>{error}</p>}

      {data && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            {Object.entries(data.totals).map(([platform, count]) => (
              <div key={platform} style={{ borderRadius: "12px", background: "#17161a", padding: "16px" }}>
                <p style={{ fontSize: "12px", color: "#8a8790", textTransform: "capitalize" }}>{platform}</p>
                <p style={{ fontSize: "24px", marginTop: "4px" }}>{count}</p>
              </div>
            ))}
          </div>

          <div>
            <p style={{ fontSize: "12px", color: "#8a8790", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
              Last 14 days
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "14px" }}>
              {Object.entries(data.daily)
                .sort((a, b) => (a[0] < b[0] ? 1 : -1))
                .map(([day, counts]) => (
                  <div key={day} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.05)", padding: "6px 0" }}>
                    <span style={{ color: "#8a8790" }}>{day}</span>
                    <span>
                      {Object.entries(counts).map(([p, c]) => `${p}: ${c}`).join("  ·  ")}
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
