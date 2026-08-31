import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./mobile/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0e17",
          panel: "#111827",
          border: "#1f2937",
          accent: "#f59e0b",
          green: "#10b981",
          red: "#ef4444",
          text: "#e5e7eb",
          muted: "#6b7280",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
