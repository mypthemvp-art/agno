import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";
import { getJwtSecretKey, isJwtConfigured, JWT_MISCONFIGURED_MESSAGE } from "@/lib/jwt";

async function verifyToken(token: string) {
  const secret = getJwtSecretKey();
  if (!secret) {
    throw new Error(JWT_MISCONFIGURED_MESSAGE);
  }
  return jwtVerify(token, secret);
}

export async function middleware(req: NextRequest) {
  const token =
    req.headers.get("authorization")?.replace("Bearer ", "") ||
    req.cookies.get("token")?.value;

  const isApi =
    req.nextUrl.pathname.startsWith("/api/chat") ||
    req.nextUrl.pathname.startsWith("/api/billing");

  const isProtected =
    req.nextUrl.pathname.startsWith("/dashboard") || isApi;

  if (!isProtected) {
    return NextResponse.next();
  }

  if (!isJwtConfigured()) {
    if (isApi) {
      return NextResponse.json({ error: JWT_MISCONFIGURED_MESSAGE }, { status: 503 });
    }
    return NextResponse.redirect(new URL("/login?error=jwt_config", req.url));
  }

  if (!token) {
    if (isApi) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/login", req.url));
  }

  try {
    await verifyToken(token);
    return NextResponse.next();
  } catch {
    if (isApi) {
      return NextResponse.json({ error: "Token expired" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/login?error=expired", req.url));
  }
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/chat/:path*", "/api/billing/:path*"],
};
