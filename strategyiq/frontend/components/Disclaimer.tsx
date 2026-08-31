import { SEC_DISCLAIMER } from "@/lib/constants";

export function Disclaimer() {
  return (
    <p className="text-center text-xs text-terminal-muted">
      {SEC_DISCLAIMER}
    </p>
  );
}
