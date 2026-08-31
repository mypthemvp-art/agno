export const runtime = "edge";

export async function POST(req: Request) {
  const { tier } = await req.json();
  const auth = req.headers.get("authorization");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const res = await fetch(`${apiUrl}/billing/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth || "",
    },
    body: JSON.stringify({ tier }),
  });

  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const tier = url.searchParams.get("tier") || "pro";
  const auth = req.headers.get("authorization");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const res = await fetch(`${apiUrl}/billing/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth || "",
    },
    body: JSON.stringify({ tier }),
  });

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
