export const SEC_DISCLAIMER = "Financial information only, not financial advice";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type UserTier = "beginner" | "pro" | "elite";

export interface TierInfo {
  name: UserTier;
  label: string;
  price: number;
  features: string[];
}

export const TIERS: TierInfo[] = [
  {
    name: "beginner",
    label: "Beginner",
    price: 0,
    features: ["3 queries/day", "Delayed market data", "Basic screener"],
  },
  {
    name: "pro",
    label: "Pro",
    price: 29,
    features: ["Unlimited queries", "Real-time data", "Trading signals", "Grok intelligence"],
  },
  {
    name: "elite",
    label: "Elite",
    price: 79,
    features: [
      "Everything in Pro",
      "Custom agents",
      "PORT analytics (Sharpe, VaR)",
      "Portfolio management",
    ],
  },
];

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API error");
  }
  return res.json();
}
