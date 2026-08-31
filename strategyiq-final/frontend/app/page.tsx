"use client";

import { useState } from "react";
import { Chart } from "@/components/Chart";
import { PortGo } from "@/components/PortGo";
import { AIAgent } from "@/components/AIAgent";
import { Signals } from "@/components/Signals";
import { AuthBar } from "@/components/AuthBar";
import { EqSGo } from "@/components/EqSGo";

type Panel = "market" | "eqs" | "port" | "news" | "chat";

const NAV: { id: Panel; label: string }[] = [
  { id: "market", label: "MKT" },
  { id: "eqs", label: "EQS" },
  { id: "port", label: "PORT" },
  { id: "news", label: "NEWS" },
  { id: "chat", label: "CHAT" },
];

export default function DesktopPage() {
  const [panel, setPanel] = useState<Panel>("market");

  return (
    <div className="min-h-screen grid grid-rows-[auto_1fr]">
      <header className="border-b border-terminal-border bg-terminal-panel px-6 py-3 flex justify-between">
        <h1 className="text-terminal-accent font-bold text-xl tracking-wider">StrategyIQ</h1>
        <nav className="flex gap-4 text-sm text-terminal-muted items-center">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setPanel(item.id)}
              className={
                panel === item.id
                  ? "text-terminal-accent font-semibold"
                  : "hover:text-terminal-text"
              }
            >
              {item.label}
            </button>
          ))}
          <AuthBar />
        </nav>
      </header>

      <main className="grid grid-cols-12 gap-3 p-3">
        {panel === "eqs" ? (
          <section className="col-span-12">
            <EqSGo />
          </section>
        ) : (
          <>
            <section className="col-span-8 space-y-3">
              {panel === "market" && (
                <>
                  <Chart symbol="AAPL" />
                  <Signals />
                </>
              )}
              {panel === "news" && <Signals />}
              {panel === "port" && <PortGo />}
              {panel === "chat" && <AIAgent />}
            </section>
            <aside className="col-span-4 space-y-3">
              {panel !== "port" && <PortGo />}
              {panel !== "chat" && <AIAgent />}
              {panel === "port" && <Signals />}
              {panel === "chat" && <Chart symbol="AAPL" />}
            </aside>
          </>
        )}
      </main>
    </div>
  );
}
