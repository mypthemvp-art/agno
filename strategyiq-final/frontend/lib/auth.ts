import { API_URL, SEC_DISCLAIMER } from "./constants";

const TOKEN_KEY = "strategyiq_token";
const TIER_KEY = "strategyiq_tier";

export interface AuthSession {
  token: string;
  tier: string;
}

export function getSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem(TOKEN_KEY);
  const tier = localStorage.getItem(TIER_KEY);
  if (!token) return null;
  return { token, tier: tier || "beginner" };
}

export function saveSession(token: string, tier: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TIER_KEY, tier);
  // Legacy keys used by AIAgent
  localStorage.setItem("token", token);
  localStorage.setItem("tier", tier);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TIER_KEY);
  localStorage.removeItem("token");
  localStorage.removeItem("tier");
}

export async function register(email: string, password: string): Promise<AuthSession> {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Registration failed");
  saveSession(data.access_token, data.tier);
  return { token: data.access_token, tier: data.tier };
}

export async function login(email: string, password: string): Promise<AuthSession> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");
  saveSession(data.access_token, data.tier);
  return { token: data.access_token, tier: data.tier };
}

export { SEC_DISCLAIMER };
