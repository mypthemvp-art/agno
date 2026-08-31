"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/market", label: "Market" },
  { href: "/eqs", label: "EQS" },
  { href: "/port", label: "PORT" },
  { href: "/grok", label: "Grok" },
  { href: "/billing", label: "Billing" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-terminal-border bg-terminal-panel px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <Link href="/" className="text-terminal-accent font-bold text-lg tracking-wider">
          StrategyIQ
        </Link>
        <div className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                pathname === item.href
                  ? "bg-terminal-accent/20 text-terminal-accent"
                  : "text-terminal-muted hover:text-terminal-text"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-terminal-muted">Tier:</span>
        <TierBadge tier="beginner" />
      </div>
    </nav>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    beginner: "text-terminal-muted border-terminal-muted",
    pro: "text-terminal-accent border-terminal-accent",
    elite: "text-purple-400 border-purple-400",
  };
  return (
    <span
      className={`text-xs uppercase border px-2 py-0.5 rounded ${colors[tier] || colors.beginner}`}
    >
      {tier}
    </span>
  );
}
