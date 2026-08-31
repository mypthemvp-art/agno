import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.FASTAPI_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  const tier = request.headers.get("x-user-tier");

  if (!authorization) {
    return NextResponse.json({ detail: "Authorization required" }, { status: 401 });
  }

  const body = await request.text();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: authorization,
  };
  if (tier) headers["X-User-Tier"] = tier;

  const upstream = await fetch(`${API_URL}/ai/agent`, { method: "POST", headers, body });
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") || "application/json" },
  });
}
