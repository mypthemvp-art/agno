"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";

export function Chart({ symbol }: { symbol: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "#111827" }, textColor: "#e5e7eb" },
      width: ref.current.clientWidth,
      height: 320,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
    });
    const data = Array.from({ length: 60 }, (_, i) => {
      const base = 180 + Math.sin(i / 4) * 8;
      const open = base + (Math.random() - 0.5);
      const close = base + (Math.random() - 0.5);
      const d = new Date(2025, 5, i + 1);
      return {
        time: d.toISOString().split("T")[0] as `${number}-${number}-${number}`,
        open,
        high: Math.max(open, close) + 1,
        low: Math.min(open, close) - 1,
        close,
      };
    });
    series.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [symbol]);

  return (
    <div className="panel">
      <h2 className="text-terminal-accent font-semibold mb-2">{symbol}</h2>
      <div ref={ref} />
    </div>
  );
}
