export const runtime = "edge";
export const dynamic = "force-dynamic";

import { jwtVerify } from "jose";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

type Tier = "beginner" | "pro" | "elite";

const SEC_DISCLAIMER = "Financial information only, not financial advice";

function getRedis() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Redis({ url, token });
}

function getRatelimit() {
  const redis = getRedis();
  if (!redis) return null;
  return new Ratelimit({
    redis,
    limiter: Ratelimit.slidingWindow(3, "1 d"),
    prefix: "strategyiq_chat",
  });
}

async function verifyAuth(
  request: Request
): Promise<{ userId: string; tier: Tier; email: string; token: string } | null> {
  const auth = request.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) return null;
  const token = auth.replace("Bearer ", "");
  try {
    const secret = new TextEncoder().encode(process.env.JWT_SECRET!);
    const { payload } = await jwtVerify(token, secret);
    return {
      userId: payload.sub as string,
      tier: (payload.tier as Tier) || "beginner",
      email: (payload.email as string) || "",
      token,
    };
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  try {
    const auth = await verifyAuth(request);
    if (!auth) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const { userId, tier, token } = auth;
    const body = await request.json();
    const prompt =
      body.prompt ||
      body.messages?.find((m: { role: string }) => m.role === "user")?.content ||
      "";
    const symbol = body.symbol || "AAPL";
    const asset_class = body.asset_class || "stock";
    const stream = body.stream !== false;

    if (tier === "beginner") {
      const ratelimit = getRatelimit();
      if (ratelimit) {
        const { success } = await ratelimit.limit(`beginner_${userId}`);
        if (!success) {
          return new Response(
            JSON.stringify({
              error: "Free tier limit 3/day",
              upgrade_required: true,
              checkout_url: "/api/billing/checkout?tier=pro",
              tier,
              disclaimer: SEC_DISCLAIMER,
            }),
            { status: 429, headers: { "Content-Type": "application/json" } }
          );
        }
      }
    }

    const fastApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const upstreamHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-User-Tier": tier,
      "X-User-Id": userId,
    };

    if (stream) {
      const upstream = await fetch(`${fastApiUrl}/ai/agent/stream`, {
        method: "POST",
        headers: upstreamHeaders,
        body: JSON.stringify({ prompt, symbol, asset_class, tier, user_id: userId }),
      });

      if (!upstream.body) {
        const data = await upstream.json();
        return new Response(JSON.stringify(data), {
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(upstream.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
          "X-Tier": tier,
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

    const res = await fetch(`${fastApiUrl}/ai/agent`, {
      method: "POST",
      headers: upstreamHeaders,
      body: JSON.stringify({
        prompt,
        symbol,
        asset_class,
        tier,
        messages: [{ role: "user", content: prompt }],
      }),
    });
    const data = await res.json();
    return new Response(
      JSON.stringify({ ...data, tier, userId, disclaimer: SEC_DISCLAIMER }),
      { headers: { "Content-Type": "application/json", "X-Tier": tier } }
    );
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return new Response(JSON.stringify({ error: "Internal error", message }), {
      status: 500,
    });
  }
}

export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}
