"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { login, register, SEC_DISCLAIMER } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={submit} className="panel w-full max-w-md space-y-4">
        <h1 className="text-terminal-accent text-xl font-bold">StrategyIQ</h1>
        <p className="text-sm text-terminal-muted">
          {mode === "login" ? "Sign in to your terminal" : "Create a Beginner account (free)"}
        </p>

        <input
          type="email"
          required
          placeholder="Email"
          className="w-full bg-terminal-bg border border-terminal-border rounded px-3 py-2 text-sm"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder="Password (min 8 chars)"
          className="w-full bg-terminal-bg border border-terminal-border rounded px-3 py-2 text-sm"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <p className="text-terminal-red text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-terminal-accent text-terminal-bg py-2 rounded font-semibold text-sm"
        >
          {loading ? "..." : mode === "login" ? "Sign In" : "Register"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="w-full text-sm text-terminal-muted hover:text-terminal-text"
        >
          {mode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}
        </button>

        <p className="text-xs text-terminal-muted text-center">{SEC_DISCLAIMER}</p>
      </form>
    </div>
  );
}
