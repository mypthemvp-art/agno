"use client";

import { useState } from "react";
import { API_URL, SEC_DISCLAIMER } from "@/lib/constants";
import { getSession } from "@/lib/auth";

interface ScreenerRow {
  symbol?: string;
  companyName?: string;
  price?: number;
  marketCap?: number;
  pe?: number;
  sector?: string;
  volume?: number;
  beta?: number;
}

const PRESETS: Record<string, Record<string, string>> = {
  value: {
    market_cap_more_than: "1000000000",
    pe_lower_than: "15",
    pb_lower_than: "2",
    is_actively_trading: "true",
  },
  growth: {
    market_cap_more_than: "2000000000",
    revenue_growth_more_than: "0.15",
    eps_growth_more_than: "0.1",
    is_actively_trading: "true",
  },
  dividend: {
    market_cap_more_than: "5000000000",
    dividend_yield_more_than: "0.02",
    debt_to_equity_lower_than: "1.5",
    is_actively_trading: "true",
  },
};

function formatCap(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  return value.toLocaleString();
}

export function EqSGo() {
  const [filters, setFilters] = useState<Record<string, string>>({
    market_cap_more_than: "1000000000",
    pe_lower_than: "30",
    sector: "",
    limit: "50",
  });
  const [results, setResults] = useState<ScreenerRow[]>([]);
  const [filterNames, setFilterNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [cached, setCached] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);

  const updateFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const applyPreset = (name: keyof typeof PRESETS) => {
    setFilters({ ...PRESETS[name], limit: filters.limit || "50" });
  };

  const buildBody = (): Record<string, unknown> => {
    const body: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(filters)) {
      if (val === "") continue;
      if (val === "true") {
        body[key] = true;
        continue;
      }
      if (val === "false") {
        body[key] = false;
        continue;
      }
      const num = Number(val);
      body[key] = Number.isNaN(num) ? val : num;
    }
    return body;
  };

  const authHeaders = (): HeadersInit => {
    const session = getSession();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (session?.token) {
      headers.Authorization = `Bearer ${session.token}`;
    }
    return headers;
  };

  const loadFilterDefs = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/eqs/filters`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load filters");
      setFilterNames(data.filters || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load filters");
    }
  };

  const runScreener = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/eqs/screen`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(buildBody()),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Screener failed — sign in required");
      }
      setResults(data.results || []);
      setCached(Boolean(data.cached));
      setCount(data.count ?? (data.results || []).length);
    } catch (err) {
      setResults([]);
      setCount(0);
      setError(err instanceof Error ? err.message : "Screener unavailable");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-terminal-accent font-semibold">EQS &lt;GO&gt;</h2>
          <p className="text-xs text-terminal-muted">50 filters, 15min Redis cache, FMP licensed data</p>
        </div>
        {cached && (
          <span className="text-xs border border-terminal-border text-terminal-muted px-2 py-0.5 rounded">
            Cached
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => applyPreset("value")} className="text-xs border border-terminal-border px-2 py-1 rounded text-terminal-muted hover:text-terminal-text">
          Value
        </button>
        <button type="button" onClick={() => applyPreset("growth")} className="text-xs border border-terminal-border px-2 py-1 rounded text-terminal-muted hover:text-terminal-text">
          Growth
        </button>
        <button type="button" onClick={() => applyPreset("dividend")} className="text-xs border border-terminal-border px-2 py-1 rounded text-terminal-muted hover:text-terminal-text">
          Dividend
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <FilterInput label="Min Market Cap" value={filters.market_cap_more_than || ""} onChange={(v) => updateFilter("market_cap_more_than", v)} />
        <FilterInput label="Max P/E" value={filters.pe_lower_than || ""} onChange={(v) => updateFilter("pe_lower_than", v)} />
        <FilterInput label="Min ROE" value={filters.roe_more_than || ""} onChange={(v) => updateFilter("roe_more_than", v)} />
        <FilterInput label="Max Debt/Equity" value={filters.debt_to_equity_lower_than || ""} onChange={(v) => updateFilter("debt_to_equity_lower_than", v)} />
        <FilterInput label="Sector" value={filters.sector || ""} onChange={(v) => updateFilter("sector", v)} />
        <FilterInput label="Limit" value={filters.limit || "50"} onChange={(v) => updateFilter("limit", v)} />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={runScreener}
          disabled={loading}
          className="bg-terminal-accent text-terminal-bg px-3 py-1 rounded text-sm font-semibold disabled:opacity-60"
        >
          {loading ? "Screening..." : "Run Screener"}
        </button>
        <button
          type="button"
          onClick={loadFilterDefs}
          className="border border-terminal-border text-terminal-muted px-3 py-1 rounded text-sm hover:text-terminal-text"
        >
          Show All Filters
        </button>
        {count > 0 && <span className="text-xs text-terminal-muted self-center">{count} results</span>}
      </div>

      {error && <p className="text-sm text-terminal-red">{error}</p>}

      {filterNames.length > 0 && (
        <div className="border border-terminal-border/60 rounded p-2 max-h-28 overflow-y-auto">
          <p className="text-xs text-terminal-muted mb-1">Available filters ({filterNames.length})</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-1 text-xs text-terminal-muted">
            {filterNames.map((name) => (
              <span key={name}>{name}</span>
            ))}
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-terminal-muted border-b border-terminal-border">
                <th className="text-left py-1">Symbol</th>
                <th className="text-right py-1">Price</th>
                <th className="text-right py-1">Market Cap</th>
                <th className="text-right py-1">P/E</th>
                <th className="text-right py-1">Beta</th>
                <th className="text-left py-1 pl-3">Sector</th>
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 25).map((row, index) => (
                <tr key={`${row.symbol || "row"}-${index}`} className="border-b border-terminal-border/40">
                  <td className="py-2 font-medium">{row.symbol || String(row.companyName || "-")}</td>
                  <td className="text-right">{row.price != null ? Number(row.price).toFixed(2) : "-"}</td>
                  <td className="text-right">{formatCap(row.marketCap != null ? Number(row.marketCap) : undefined)}</td>
                  <td className="text-right">{row.pe != null ? Number(row.pe).toFixed(1) : "-"}</td>
                  <td className="text-right">{row.beta != null ? Number(row.beta).toFixed(2) : "-"}</td>
                  <td className="pl-3 text-terminal-muted">{row.sector || "-"}</td>
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
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs text-terminal-muted block mb-1">{label}</span>
      <input
        className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
