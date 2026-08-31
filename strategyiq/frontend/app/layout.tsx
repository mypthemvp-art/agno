import type { Metadata } from "next";
import "./globals.css";
import { Disclaimer } from "@/components/Disclaimer";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "StrategyIQ — Retail Terminal",
  description: "Commercial Bloomberg Terminal replica for retail investors",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="min-h-screen p-4">{children}</main>
        <footer className="border-t border-terminal-border p-4">
          <Disclaimer />
        </footer>
      </body>
    </html>
  );
}
