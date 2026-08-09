export interface Env {
  BUCKET: R2Bucket;
}

const CORS_HEADERS: HeadersInit = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...CORS_HEADERS,
    },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/api/health") {
      try {
        const object = await env.BUCKET.head("home_feed.json");
        return jsonResponse({
          ok: true,
          r2: object
            ? {
                key: "home_feed.json",
                size: object.size,
                uploaded: object.uploaded.toISOString(),
              }
            : null,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResponse({ ok: false, error: message }, 500);
      }
    }

    return jsonResponse({ error: "Not found" }, 404);
  },
};
