import type { Metadata } from "next";
import "./globals.css";
import { SEC_DISCLAIMER } from "@/lib/constants";

export const metadata: Metadata = {
  title: "StrategyIQ Terminal",
  description: "Bloomberg Terminal replica for retail",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer className="p-4 text-center text-xs text-terminal-muted border-t border-terminal-border">
          {SEC_DISCLAIMER}
        </footer>
      </body>
    </html>
  );
}
