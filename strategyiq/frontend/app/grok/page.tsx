"use client";

import { useState } from "react";
import { SEC_DISCLAIMER, apiFetch } from "@/lib/constants";

export default function GrokPage() {
  const [breakingTopic, setBreakingTopic] = useState("markets");
  const [trendingSymbols, setTrendingSymbols] = useState("AAPL, TSLA, NVDA");
  const [breakingResult, setBreakingResult] = useState<string | null>(null);
  const [trendingResult, setTrendingResult] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const queryBreaking = async () => {
    setLoading("breaking");
    try {
      const data = await apiFetch<{ response: string }>("/grok/breaking", {
        method: "POST",
        body: JSON.stringify({ topic: breakingTopic }),
      });
      setBreakingResult(data.response);
    } catch (err) {
      setBreakingResult(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(null);
    }
  };

  const queryTrending = async () => {
    setLoading("trending");
    try {
      const symbols = trendingSymbols
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const data = await apiFetch<{ response: string }>("/grok/trending", {
        method: "POST",
        body: JSON.stringify({ symbols }),
      });
      setTrendingResult(data.response);
    } catch (err) {
      setTrendingResult(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-terminal-accent">Grok Intelligence</h1>
        <p className="text-terminal-muted text-sm">
          Breaking news and trending market queries routed to Grok
        </p>
      </header>

      <div className="panel space-y-4">
        <h2 className="font-semibold">Breaking News</h2>
        <div className="flex gap-3">
          <input
            className="input-field flex-1"
            value={breakingTopic}
            onChange={(e) => setBreakingTopic(e.target.value)}
            placeholder="Topic (e.g. markets, crypto, tech)"
          />
          <button
            onClick={queryBreaking}
            disabled={loading === "breaking"}
            className="btn-primary text-sm"
          >
            {loading === "breaking" ? "Querying..." : "Get Breaking"}
          </button>
        </div>
        {breakingResult && (
          <div className="bg-terminal-bg rounded p-4 text-sm whitespace-pre-wrap">
            {breakingResult}
          </div>
        )}
      </div>

      <div className="panel space-y-4">
        <h2 className="font-semibold">Trending Markets</h2>
        <div className="flex gap-3">
          <input
            className="input-field flex-1"
            value={trendingSymbols}
            onChange={(e) => setTrendingSymbols(e.target.value)}
            placeholder="Symbols (comma-separated)"
          />
          <button
            onClick={queryTrending}
            disabled={loading === "trending"}
            className="btn-primary text-sm"
          >
            {loading === "trending" ? "Querying..." : "Get Trending"}
          </button>
        </div>
        {trendingResult && (
          <div className="bg-terminal-bg rounded p-4 text-sm whitespace-pre-wrap">
            {trendingResult}
          </div>
        )}
      </div>

      <p className="text-xs text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}
