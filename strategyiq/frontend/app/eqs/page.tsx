"use client";

import { useState } from "react";
import { SEC_DISCLAIMER, apiFetch } from "@/lib/constants";

interface FilterDef {
  name: string;
  description: string;
}

export default function EQSPage() {
  const [filters, setFilters] = useState<Record<string, string>>({
    market_cap_more_than: "1000000000",
    pe_lower_than: "30",
    sector: "",
  });
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [filterDefs, setFilterDefs] = useState<FilterDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [cached, setCached] = useState(false);

  const loadFilterDefs = async () => {
    try {
      const data = await apiFetch<{ filters: FilterDef[]; filter_count: number }>(
        "/eqs/filters"
      );
      setFilterDefs(data.filters);
    } catch {
      /* auth required in production */
    }
  };

  const runScreener = async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(filters)) {
        if (val === "") continue;
        const num = Number(val);
        body[key] = isNaN(num) ? val : num;
      }
      const data = await apiFetch<{ results: Record<string, unknown>[]; cached: boolean }>(
        "/eqs/screen",
        { method: "POST", body: JSON.stringify(body) }
      );
      setResults(data.results);
      setCached(data.cached);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-terminal-accent">EQS — Equity Screener</h1>
        <p className="text-terminal-muted text-sm">
          50 filters, cached 15min in Redis. Data via FMP API.
        </p>
      </header>

      <div className="panel space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <FilterInput
            label="Min Market Cap"
            value={filters.market_cap_more_than}
            onChange={(v) => setFilters({ ...filters, market_cap_more_than: v })}
          />
          <FilterInput
            label="Max P/E"
            value={filters.pe_lower_than}
            onChange={(v) => setFilters({ ...filters, pe_lower_than: v })}
          />
          <FilterInput
            label="Sector"
            value={filters.sector}
            onChange={(v) => setFilters({ ...filters, sector: v })}
          />
          <FilterInput
            label="Min ROE"
            value={filters.roe_more_than || ""}
            onChange={(v) => setFilters({ ...filters, roe_more_than: v })}
          />
        </div>

        <div className="flex gap-3">
          <button onClick={runScreener} disabled={loading} className="btn-primary text-sm">
            {loading ? "Screening..." : "Run Screener"}
          </button>
          <button onClick={loadFilterDefs} className="btn-secondary text-sm">
            Load All 50 Filters
          </button>
          {cached && <span className="text-xs text-terminal-muted self-center">Cached result</span>}
        </div>
      </div>

      {filterDefs.length > 0 && (
        <div className="panel">
          <h3 className="text-sm font-semibold mb-2">
            Available Filters ({filterDefs.length})
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1 text-xs text-terminal-muted max-h-48 overflow-y-auto">
            {filterDefs.map((f) => (
              <span key={f.name}>{f.name}</span>
            ))}
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-terminal-muted border-b border-terminal-border">
                <th className="text-left py-2">Symbol</th>
                <th className="text-right py-2">Price</th>
                <th className="text-right py-2">Market Cap</th>
                <th className="text-right py-2">P/E</th>
                <th className="text-right py-2">Sector</th>
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 20).map((r, i) => (
                <tr key={i} className="border-b border-terminal-border/50">
                  <td className="py-2">{String(r.symbol || r.companyName || "-")}</td>
                  <td className="text-right">{String(r.price ?? "-")}</td>
                  <td className="text-right">{String(r.marketCap ?? "-")}</td>
                  <td className="text-right">{String(r.pe ?? "-")}</td>
                  <td className="text-right">{String(r.sector ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}

function FilterInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="text-xs text-terminal-muted block mb-1">{label}</label>
      <input className="input-field w-full text-sm" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
