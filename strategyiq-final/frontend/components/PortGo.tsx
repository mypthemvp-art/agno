"use client";

import { useState } from "react";
import { API_URL, SEC_DISCLAIMER } from "@/lib/constants";

interface Metrics {
  sharpe_ratio: number;
  var_95: number;
  total_return: number;
  monte_carlo_var?: number;
}

function monteCarloVar(dailyVol: number, days: number = 1, simulations: number = 10000): number {
  const returns: number[] = [];
  for (let i = 0; i < simulations; i++) {
    const shock = (Math.random() - 0.5) * 2 * dailyVol * Math.sqrt(days);
    returns.push(shock);
  }
  returns.sort((a, b) => a - b);
  return returns[Math.floor(0.05 * simulations)];
}

export function PortGo() {
  const [holdings, setHoldings] = useState([
    { symbol: "AAPL", weight: 0.4 },
    { symbol: "MSFT", weight: 0.35 },
    { symbol: "NVDA", weight: 0.25 },
  ]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/port/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings, lookback_days: 252 }),
      });
      if (res.ok) {
        const data = await res.json();
        const mcVar = monteCarloVar(data.std_daily_return || 0.02);
        setMetrics({ ...data, monte_carlo_var: mcVar });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel space-y-3">
      <h2 className="text-terminal-accent font-semibold">PORT &lt;GO&gt;</h2>
      <p className="text-xs text-terminal-muted">Sharpe = sqrt(252) x mean/std. VaR = 5th pct.</p>
      {holdings.map((h, i) => (
        <div key={i} className="flex gap-2 text-sm">
          <span className="w-16">{h.symbol}</span>
          <span>{(h.weight * 100).toFixed(0)}%</span>
        </div>
      ))}
      <button
        onClick={analyze}
        disabled={loading}
        className="bg-terminal-accent text-terminal-bg px-3 py-1 rounded text-sm font-semibold"
      >
        {loading ? "Analyzing..." : "Analyze"}
      </button>
      {metrics && (
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Sharpe: <strong>{metrics.sharpe_ratio}</strong></div>
          <div>VaR 95%: <strong>{(metrics.var_95 * 100).toFixed(2)}%</strong></div>
          <div>Return: <strong>{(metrics.total_return * 100).toFixed(1)}%</strong></div>
          <div>MC VaR: <strong>{((metrics.monte_carlo_var || 0) * 100).toFixed(2)}%</strong></div>
        </div>
      )}
      <p className="text-xs text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}
