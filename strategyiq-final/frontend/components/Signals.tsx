"use client";

const SIGNALS = [
  { symbol: "NVDA", signal: "BUY", strength: 82, reason: "Momentum breakout above 200DMA" },
  { symbol: "TSLA", signal: "SELL", strength: 67, reason: "RSI overbought + volume divergence" },
  { symbol: "AAPL", signal: "HOLD", strength: 54, reason: "Range-bound, awaiting earnings" },
  { symbol: "BTC", signal: "BUY", strength: 71, reason: "ETF inflow trend + halving cycle" },
];

export function Signals() {
  return (
    <div className="panel">
      <h2 className="text-terminal-accent font-semibold mb-3">Pro Signals</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-terminal-muted border-b border-terminal-border">
            <th className="text-left py-1">Symbol</th>
            <th className="text-left py-1">Signal</th>
            <th className="text-right py-1">Strength</th>
            <th className="text-left py-1 pl-4">Reason</th>
          </tr>
        </thead>
        <tbody>
          {SIGNALS.map((s) => (
            <tr key={s.symbol} className="border-b border-terminal-border/40">
              <td className="py-2">{s.symbol}</td>
              <td className={s.signal === "BUY" ? "text-terminal-green" : s.signal === "SELL" ? "text-terminal-red" : ""}>
                {s.signal}
              </td>
              <td className="text-right">{s.strength}</td>
              <td className="pl-4 text-terminal-muted">{s.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
