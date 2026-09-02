const INSECURE_SECRETS = new Set(["", "change_this_64_random_chars", "changeme", "secret"]);

/** True when JWT_SECRET is set to a non-default value (min 16 chars). */
export function isJwtConfigured(): boolean {
  const raw = process.env.JWT_SECRET?.trim();
  if (!raw || raw.length < 16) return false;
  return !INSECURE_SECRETS.has(raw);
}

/** Returns the encoded JWT secret, or null when misconfigured. */
export function getJwtSecretKey(): Uint8Array | null {
  if (!isJwtConfigured()) return null;
  return new TextEncoder().encode(process.env.JWT_SECRET!.trim());
}

export const JWT_MISCONFIGURED_MESSAGE =
  "JWT_SECRET is not configured. Set a unique secret of at least 16 characters.";
