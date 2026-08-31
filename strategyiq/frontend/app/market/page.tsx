"use client";

import { useState } from "react";
import { TradingChart } from "@/components/TradingChart";
import { SEC_DISCLAIMER } from "@/lib/constants";

const SAMPLE_DATA = Array.from({ length: 60 }, (_, i) => {
  const base = 150 + Math.sin(i / 5) * 10;
  const open = base + (Math.random() - 0.5) * 2;
  const close = base + (Math.random() - 0.5) * 2;
  const high = Math.max(open, close) + Math.random() * 2;
  const low = Math.min(open, close) - Math.random() * 2;
  const date = new Date(2025, 0, i + 1);
  return {
    time: date.toISOString().split("T")[0],
    open: +open.toFixed(2),
    high: +high.toFixed(2),
    low: +low.toFixed(2),
    close: +close.toFixed(2),
  };
});

export default function MarketPage() {
  const [symbol, setSymbol] = useState("AAPL");

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-terminal-accent">Market Data</h1>
        <input
          className="input-field w-32"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="Symbol"
        />
      </div>

      <div className="panel">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold">{symbol}</h2>
          <span className="text-xs text-terminal-muted">Data via Polygon.io API</span>
        </div>
        <TradingChart data={SAMPLE_DATA} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="panel">
          <p className="text-terminal-muted text-xs">Last Price</p>
          <p className="text-2xl font-bold text-terminal-green">$182.45</p>
        </div>
        <div className="panel">
          <p className="text-terminal-muted text-xs">Change</p>
          <p className="text-2xl font-bold text-terminal-green">+1.23%</p>
        </div>
        <div className="panel">
          <p className="text-terminal-muted text-xs">Volume</p>
          <p className="text-2xl font-bold">52.4M</p>
        </div>
      </div>

      <p className="text-xs text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}
