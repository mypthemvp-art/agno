import { PortGo } from "@/components/PortGo";
import { SEC_DISCLAIMER } from "@/lib/constants";

export const metadata = {
  manifest: "/manifest.json",
  themeColor: "#0a0e17",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function MobilePage() {
  return (
    <div className="min-h-screen p-4 space-y-4">
      <header>
        <h1 className="text-terminal-accent font-bold text-lg">StrategyIQ Mobile</h1>
        <p className="text-xs text-terminal-muted">PWA — swipe-friendly terminal</p>
      </header>
      <PortGo />
      <p className="text-xs text-center text-terminal-muted">{SEC_DISCLAIMER}</p>
    </div>
  );
}
