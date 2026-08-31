import { Chart } from "@/components/Chart";
import { PortGo } from "@/components/PortGo";
import { AIAgent } from "@/components/AIAgent";
import { Signals } from "@/components/Signals";

export default function DesktopPage() {
  return (
    <div className="min-h-screen grid grid-rows-[auto_1fr]">
      <header className="border-b border-terminal-border bg-terminal-panel px-6 py-3 flex justify-between">
        <h1 className="text-terminal-accent font-bold text-xl tracking-wider">StrategyIQ</h1>
        <nav className="flex gap-4 text-sm text-terminal-muted">
          <span>EQS</span>
          <span>PORT</span>
          <span>NEWS</span>
          <span>CHAT</span>
        </nav>
      </header>

      <main className="grid grid-cols-12 gap-3 p-3">
        <section className="col-span-8 space-y-3">
          <Chart symbol="AAPL" />
          <Signals />
        </section>
        <aside className="col-span-4 space-y-3">
          <PortGo />
          <AIAgent />
        </aside>
      </main>
    </div>
  );
}
