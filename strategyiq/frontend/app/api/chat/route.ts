import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.FASTAPI_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  const tier = request.headers.get("x-user-tier") || request.headers.get("X-User-Tier");

  if (!authorization) {
    return NextResponse.json({ detail: "Authorization header required" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: authorization,
  };

  if (tier) {
    headers["X-User-Tier"] = tier;
  }

  try {
    const upstream = await fetch(`${API_URL}/ai/agent`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const responseBody = await upstream.text();
    const contentType = upstream.headers.get("content-type") || "application/json";

    return new NextResponse(responseBody, {
      status: upstream.status,
      headers: { "Content-Type": contentType },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upstream request failed";
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}

export async function GET() {
  return NextResponse.json({
    endpoint: "/api/chat",
    proxies_to: `${API_URL}/ai/agent`,
    required_headers: ["Authorization", "X-User-Tier (optional)"],
    disclaimer: "Financial information only, not financial advice",
  });
}
