"use client";

import { useState } from "react";
import { SEC_DISCLAIMER, apiFetch } from "@/lib/constants";

interface Holding {
  symbol: string;
  weight: number;
}

interface PortfolioMetrics {
  sharpe_ratio: number;
  var_95: number;
  mean_daily_return: number;
  std_daily_return: number;
  total_return: number;
  holdings: { symbol: string; weight: number; mean_return: number; volatility: number }[];
  disclaimer: string;
}

/**
 * PortGo — Portfolio analytics component.
 * Sharpe = sqrt(252) * mean / std
 * VaR = 5th percentile of daily returns
 */
export function PortGo() {
  const [holdings, setHoldings] = useState<Holding[]>([
    { symbol: "AAPL", weight: 0.4 },
    { symbol: "MSFT", weight: 0.3 },
    { symbol: "GOOGL", weight: 0.3 },
  ]);
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addHolding = () => {
    setHoldings([...holdings, { symbol: "", weight: 0 }]);
  };

  const updateHolding = (index: number, field: keyof Holding, value: string | number) => {
    const updated = [...holdings];
    updated[index] = { ...updated[index], [field]: value };
    setHoldings(updated);
  };

  const removeHolding = (index: number) => {
    setHoldings(holdings.filter((_, i) => i !== index));
  };

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<PortfolioMetrics>("/port/analyze", {
        method: "POST",
        body: JSON.stringify({ holdings, lookback_days: 252 }),
      });
      setMetrics(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const totalWeight = holdings.reduce((sum, h) => sum + h.weight, 0);

  return (
    <div className="space-y-6">
      <div className="panel">
        <h2 className="text-terminal-accent text-lg font-semibold mb-4">
          PORT — Portfolio Analytics
        </h2>
        <p className="text-terminal-muted text-sm mb-4">
          Elite tier required. Sharpe = sqrt(252) x mean/std. VaR = 5th percentile.
        </p>

        <div className="space-y-3 mb-4">
          {holdings.map((h, i) => (
            <div key={i} className="flex gap-3 items-center">
              <input
                className="input-field w-28"
                placeholder="Symbol"
                value={h.symbol}
                onChange={(e) => updateHolding(i, "symbol", e.target.value.toUpperCase())}
              />
              <input
                className="input-field w-24"
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={h.weight}
                onChange={(e) => updateHolding(i, "weight", parseFloat(e.target.value) || 0)}
              />
              <button
                onClick={() => removeHolding(i)}
                className="text-terminal-red text-sm hover:underline"
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        <div className="flex gap-3 items-center">
          <button onClick={addHolding} className="btn-secondary text-sm">
            Add Holding
          </button>
          <button onClick={analyze} disabled={loading} className="btn-primary text-sm">
            {loading ? "Analyzing..." : "Analyze Portfolio"}
          </button>
          <span
            className={`text-sm ${Math.abs(totalWeight - 1) < 0.01 ? "text-terminal-green" : "text-terminal-red"}`}
          >
            Weight: {(totalWeight * 100).toFixed(1)}%
          </span>
        </div>

        {error && <p className="text-terminal-red text-sm mt-3">{error}</p>}
      </div>

      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Sharpe Ratio" value={metrics.sharpe_ratio.toFixed(4)} />
          <MetricCard
            label="VaR (95%)"
            value={`${(metrics.var_95 * 100).toFixed(2)}%`}
            negative={metrics.var_95 < 0}
          />
          <MetricCard
            label="Total Return"
            value={`${(metrics.total_return * 100).toFixed(2)}%`}
            positive={metrics.total_return > 0}
            negative={metrics.total_return < 0}
          />
          <MetricCard
            label="Daily Volatility"
            value={`${(metrics.std_daily_return * 100).toFixed(3)}%`}
          />
        </div>
      )}

      {metrics && (
        <div className="panel">
          <h3 className="text-sm font-semibold mb-3">Holdings Breakdown</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-terminal-muted border-b border-terminal-border">
                <th className="text-left py-2">Symbol</th>
                <th className="text-right py-2">Weight</th>
                <th className="text-right py-2">Mean Return</th>
                <th className="text-right py-2">Volatility</th>
              </tr>
            </thead>
            <tbody>
              {metrics.holdings.map((h) => (
                <tr key={h.symbol} className="border-b border-terminal-border/50">
                  <td className="py-2">{h.symbol}</td>
                  <td className="text-right">{(h.weight * 100).toFixed(1)}%</td>
                  <td className="text-right">{(h.mean_return * 100).toFixed(3)}%</td>
                  <td className="text-right">{(h.volatility * 100).toFixed(3)}%</td>
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

function MetricCard({
  label,
  value,
  positive,
  negative,
}: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
}) {
  let color = "text-terminal-text";
  if (positive) color = "text-terminal-green";
  if (negative) color = "text-terminal-red";

  return (
    <div className="panel text-center">
      <p className="text-terminal-muted text-xs mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}
