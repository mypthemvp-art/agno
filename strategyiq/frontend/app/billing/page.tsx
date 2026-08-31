"use client";

import { TIERS, SEC_DISCLAIMER } from "@/lib/constants";

export default function BillingPage() {
  const handleCheckout = async (tier: string) => {
    alert(`Stripe checkout for ${tier} tier would open here. Configure STRIPE_* env vars.`);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-terminal-accent">Billing</h1>
        <p className="text-terminal-muted text-sm">
          Manage your StrategyIQ subscription via Stripe
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TIERS.map((tier) => (
          <div
            key={tier.name}
            className={`panel ${tier.name === "pro" ? "border-terminal-accent" : ""}`}
          >
            <h3 className="text-lg font-semibold text-terminal-accent">{tier.label}</h3>
            <p className="text-3xl font-bold my-3">
              {tier.price === 0 ? "Free" : `$${tier.price}`}
              {tier.price > 0 && <span className="text-sm text-terminal-muted">/mo</span>}
            </p>
            <ul className="text-sm text-terminal-muted space-y-1 mb-4">
              {tier.features.map((f) => (
                <li key={f}>- {f}</li>
              ))}
            </ul>
            {tier.price > 0 ? (
              <button
                onClick={() => handleCheckout(tier.name)}
                className="btn-primary w-full text-sm"
              >
                Upgrade to {tier.label}
              </button>
            ) : (
              <span className="text-xs text-terminal-muted">Current plan</span>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}
