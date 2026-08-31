import Link from "next/link";
import { TIERS, SEC_DISCLAIMER } from "@/lib/constants";

export default function DashboardPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-terminal-accent mb-2">StrategyIQ Terminal</h1>
        <p className="text-terminal-muted">
          Commercial Bloomberg Terminal replica for retail investors
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ModuleCard title="Market Data" href="/market" description="Real-time quotes, charts, crypto via Polygon, CoinGecko, FMP" />
        <ModuleCard title="EQS Screener" href="/eqs" description="50-filter equity screener with 15min Redis cache" />
        <ModuleCard title="PORT Analytics" href="/port" description="Sharpe ratio, VaR, portfolio optimization (Elite)" />
        <ModuleCard title="Grok Intelligence" href="/grok" description="Breaking news and trending market analysis" />
        <ModuleCard title="Billing" href="/billing" description="Manage Pro ($29) and Elite ($79) subscriptions" />
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-4">Subscription Tiers</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {TIERS.map((tier) => (
            <div key={tier.name} className="panel">
              <h3 className="text-terminal-accent font-semibold">{tier.label}</h3>
              <p className="text-2xl font-bold my-2">
                {tier.price === 0 ? "Free" : `$${tier.price}/mo`}
              </p>
              <ul className="text-sm text-terminal-muted space-y-1">
                {tier.features.map((f) => (
                  <li key={f}>- {f}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <p className="text-xs text-terminal-muted text-center">{SEC_DISCLAIMER}</p>
    </div>
  );
}

function ModuleCard({
  title,
  href,
  description,
}: {
  title: string;
  href: string;
  description: string;
}) {
  return (
    <Link href={href} className="panel hover:border-terminal-accent transition-colors block">
      <h3 className="font-semibold text-terminal-accent">{title}</h3>
      <p className="text-sm text-terminal-muted mt-1">{description}</p>
    </Link>
  );
}
