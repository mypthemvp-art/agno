"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { API_URL, SEC_DISCLAIMER } from "@/lib/constants";
import { getSession } from "@/lib/auth";

interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface Quote {
  price?: number | null;
  change_pct?: number | null;
  volume?: number | null;
  realtime?: boolean;
  source?: string;
}

function sampleCandles(symbol: string): Candle[] {
  const seed = symbol.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return Array.from({ length: 60 }, (_, i) => {
    const base = 100 + (seed % 80) + Math.sin(i / 4) * 8;
    const open = base + ((i + seed) % 7) * 0.1 - 0.3;
    const close = base + ((i + seed) % 5) * 0.1 - 0.2;
    const d = new Date(Date.UTC(2025, 5, i + 1));
    return {
      time: d.toISOString().split("T")[0],
      open,
      high: Math.max(open, close) + 1,
      low: Math.min(open, close) - 1,
      close,
    };
  });
}

export function Chart({ symbol: initialSymbol }: { symbol: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [symbol, setSymbol] = useState(initialSymbol.toUpperCase());
  const [input, setInput] = useState(initialSymbol.toUpperCase());
  const [quote, setQuote] = useState<Quote | null>(null);
  const [status, setStatus] = useState<string>("Loading...");
  const [usingSample, setUsingSample] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "#111827" }, textColor: "#e5e7eb" },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      width: ref.current.clientWidth,
      height: 320,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const applyCandles = (candles: Candle[]) => {
      if (!seriesRef.current || candles.length === 0) return;
      seriesRef.current.setData(
        candles.map((c) => ({
          time: c.time as `${number}-${number}-${number}`,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );
      chartRef.current?.timeScale().fitContent();
    };

    const load = async () => {
      setStatus("Loading...");
      const session = getSession();
      if (!session?.token) {
        applyCandles(sampleCandles(symbol));
        setQuote(null);
        setUsingSample(true);
        setStatus("Sign in for live Polygon/FMP data");
        return;
      }

      try {
        const headers = { Authorization: `Bearer ${session.token}` };
        const [histRes, quoteRes] = await Promise.all([
          fetch(`${API_URL}/market/history/${symbol}?limit=120`, { headers }),
          fetch(`${API_URL}/market/quote/${symbol}`, { headers }),
        ]);

        if (cancelled) return;

        if (histRes.ok) {
          const hist = await histRes.json();
          applyCandles(hist.candles || []);
          setUsingSample(false);
          setStatus(hist.realtime ? "Real-time tier" : "Delayed (Beginner)");
        } else {
          applyCandles(sampleCandles(symbol));
          setUsingSample(true);
          const err = await histRes.json().catch(() => ({}));
          setStatus(typeof err.detail === "string" ? err.detail : "History unavailable — showing sample");
        }

        if (quoteRes.ok) {
          const q = await quoteRes.json();
          setQuote(q);
        } else {
          setQuote(null);
        }
      } catch {
        if (cancelled) return;
        applyCandles(sampleCandles(symbol));
        setUsingSample(true);
        setQuote(null);
        setStatus("Market API unreachable — showing sample");
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const next = input.trim().toUpperCase();
    if (next) setSymbol(next);
  };

  const changeClass =
    quote?.change_pct == null
      ? "text-terminal-muted"
      : quote.change_pct >= 0
        ? "text-terminal-green"
        : "text-terminal-red";

  return (
    <div className="panel">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <form onSubmit={onSubmit} className="flex items-center gap-2">
          <h2 className="text-terminal-accent font-semibold">{symbol}</h2>
          <input
            className="w-24 bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-sm uppercase"
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            aria-label="Symbol"
          />
          <button
            type="submit"
            className="text-xs border border-terminal-border text-terminal-muted px-2 py-1 rounded hover:text-terminal-text"
          >
            Load
          </button>
        </form>
        <span className="text-xs text-terminal-muted">{usingSample ? "Sample" : "Live"} · {status}</span>
      </div>

      {(quote?.price != null || quote?.change_pct != null) && (
        <div className="grid grid-cols-3 gap-2 mb-3 text-sm">
          <div>
            <p className="text-xs text-terminal-muted">Last</p>
            <p className="font-semibold">
              {quote.price != null ? `$${Number(quote.price).toFixed(2)}` : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-terminal-muted">Change</p>
            <p className={`font-semibold ${changeClass}`}>
              {quote.change_pct != null ? `${Number(quote.change_pct).toFixed(2)}%` : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-terminal-muted">Volume</p>
            <p className="font-semibold">
              {quote.volume != null ? Number(quote.volume).toLocaleString() : "-"}
            </p>
          </div>
        </div>
      )}

      <div ref={ref} />
      <p className="text-xs text-terminal-muted mt-2">{SEC_DISCLAIMER}</p>
    </div>
  );
}
