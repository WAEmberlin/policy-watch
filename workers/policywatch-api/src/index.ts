/**
 * PolicyWatch API Worker
 *
 * GET /api/health — R2 connectivity check
 * GET /api/search?q=&state=&limit=&offset=&date_from=&date_to= — bill search over R2 shards
 *   (q optional when date_from and/or date_to is set — date-only browse)
 *
 * Search data: prefer search_shards/*.json (compact per-jurisdiction files).
 * Largest shard is ~MA (~12–15MB compact). Shards are loaded one at a time and
 * cached in module scope with a short TTL so isolates do not hold the full
 * ~78MB home_search_bills.json (which would OOM the Worker).
 */

export interface Env {
  BUCKET: R2Bucket;
}

/** Compact on-disk shard row (short keys). */
interface ShardBill {
  n?: string;
  t?: string;
  s?: string;
  l?: string;
  a?: string;
  d?: string;
  u?: string;
  // Allow already-expanded rows if present.
  bill_number?: string;
  title?: string;
  state?: string;
  level?: string;
  latest_action?: string;
  latest_action_date?: string;
  url?: string;
}

interface SearchBill {
  bill_number: string;
  title: string;
  state: string;
  level: string;
  latest_action: string;
  latest_action_date: string;
  url: string;
  item_type: string;
  action_type: string;
}

interface ShardMeta {
  shards: string[];
  bill_count?: number;
  generated_at?: string;
}

const CACHE_TTL_MS = 10 * 60 * 1000;
const MIN_QUERY_LEN = 3;
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 50;

const ALLOWED_ORIGIN_EXACT = new Set([
  "https://policywatch.us",
  "https://www.policywatch.us",
  "https://waemberlin.github.io",
]);

let shardMetaCache: { meta: ShardMeta; loadedAt: number } | null = null;
const shardCache = new Map<string, { bills: ShardBill[]; loadedAt: number }>();
const MATCH_COLLECT_CAP = 2000;

function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  if (ALLOWED_ORIGIN_EXACT.has(origin)) return true;
  try {
    const url = new URL(origin);
    if (url.protocol === "http:" && (url.hostname === "127.0.0.1" || url.hostname === "localhost")) {
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function corsHeaders(request: Request): HeadersInit {
  const origin = request.headers.get("Origin");
  const headers: Record<string, string> = {
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
  if (origin && isAllowedOrigin(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }
  return headers;
}

function jsonResponse(request: Request, body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(request),
    },
  });
}

function normalizeStateParam(state: string): string {
  const s = state.trim();
  if (!s) return "";
  if (s.toLowerCase() === "federal" || s.toUpperCase() === "US") return "US";
  return s.toUpperCase();
}

function expandShardBill(raw: ShardBill): SearchBill {
  return {
    bill_number: raw.bill_number || raw.n || "",
    title: raw.title || raw.t || "",
    state: raw.state || raw.s || "",
    level: raw.level || raw.l || "",
    latest_action: raw.latest_action || raw.a || "",
    latest_action_date: raw.latest_action_date || raw.d || "",
    url: raw.url || raw.u || "",
    item_type: "bill_update",
    action_type: "",
  };
}

function shardStateKey(bill: ShardBill): string {
  const state = (bill.state || bill.s || "").toUpperCase();
  if (state) return state;
  const level = (bill.level || bill.l || "").toLowerCase();
  return level === "federal" ? "US" : "";
}

function billMatchesState(bill: ShardBill, stateKey: string): boolean {
  if (!stateKey) return true;
  if (stateKey === "US") {
    const level = (bill.level || bill.l || "").toLowerCase();
    const state = (bill.state || bill.s || "").toUpperCase();
    return level === "federal" || !state || state === "US";
  }
  return shardStateKey(bill) === stateKey;
}

function billSearchText(bill: ShardBill): string {
  return [bill.title || bill.t, bill.bill_number || bill.n, bill.latest_action || bill.a]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function clampInt(value: string | null, fallback: number, min: number, max: number): number {
  const n = Number.parseInt(value || "", 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

const DATE_PARAM_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Parse YYYY-MM-DD; returns null if empty/omitted, or an error string if invalid. */
function parseOptionalDateParam(value: string | null): { date: string | null; error: string | null } {
  const raw = (value || "").trim();
  if (!raw) return { date: null, error: null };
  if (!DATE_PARAM_RE.test(raw)) {
    return { date: null, error: "date_from/date_to must be YYYY-MM-DD" };
  }
  const [y, m, d] = raw.split("-").map((part) => Number.parseInt(part, 10));
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (
    !Number.isFinite(y) ||
    !Number.isFinite(m) ||
    !Number.isFinite(d) ||
    dt.getUTCFullYear() !== y ||
    dt.getUTCMonth() !== m - 1 ||
    dt.getUTCDate() !== d
  ) {
    return { date: null, error: "date_from/date_to must be a valid calendar date (YYYY-MM-DD)" };
  }
  return { date: raw, error: null };
}

function billMatchesDateRange(
  bill: ShardBill,
  dateFrom: string | null,
  dateTo: string | null
): boolean {
  if (!dateFrom && !dateTo) return true;
  const day = String(bill.latest_action_date || bill.d || "").slice(0, 10);
  if (!DATE_PARAM_RE.test(day)) return false;
  if (dateFrom && day < dateFrom) return false;
  if (dateTo && day > dateTo) return false;
  return true;
}

async function loadShardMeta(env: Env): Promise<ShardMeta> {
  const now = Date.now();
  if (shardMetaCache && now - shardMetaCache.loadedAt < CACHE_TTL_MS) {
    return shardMetaCache.meta;
  }
  const obj = await env.BUCKET.get("search_shards/meta.json");
  if (!obj) {
    throw new Error("search_shards/meta.json missing from R2");
  }
  const meta = (await obj.json()) as ShardMeta;
  if (!meta || !Array.isArray(meta.shards) || meta.shards.length === 0) {
    throw new Error("search_shards/meta.json has no shards");
  }
  shardMetaCache = { meta, loadedAt: now };
  return meta;
}

async function loadShard(env: Env, shardKey: string): Promise<ShardBill[]> {
  const now = Date.now();
  const cached = shardCache.get(shardKey);
  if (cached && now - cached.loadedAt < CACHE_TTL_MS) {
    return cached.bills;
  }

  const obj = await env.BUCKET.get(`search_shards/${shardKey}.json`);
  if (!obj) {
    throw new Error(`search_shards/${shardKey}.json missing from R2`);
  }
  const data = (await obj.json()) as { bills?: ShardBill[] } | ShardBill[];
  const bills = Array.isArray(data) ? data : data.bills || [];

  // Keep only one shard parsed in memory — MA alone is ~15MB compact JSON.
  shardCache.clear();
  shardCache.set(shardKey, { bills, loadedAt: now });

  return bills;
}

async function searchBills(
  env: Env,
  q: string,
  stateKey: string,
  limit: number,
  offset: number,
  dateFrom: string | null = null,
  dateTo: string | null = null
): Promise<{ results: SearchBill[]; total: number }> {
  const meta = await loadShardMeta(env);
  const query = q.toLowerCase();
  const hasTextQuery = query.length > 0;
  const shardKeys =
    stateKey && meta.shards.includes(stateKey) ? [stateKey] : meta.shards;

  const matched: SearchBill[] = [];
  let total = 0;
  for (const key of shardKeys) {
    const bills = await loadShard(env, key);
    for (const bill of bills) {
      if (!billMatchesState(bill, stateKey)) continue;
      if (!billMatchesDateRange(bill, dateFrom, dateTo)) continue;
      if (hasTextQuery && !billSearchText(bill).includes(query)) continue;
      total += 1;
      if (matched.length < MATCH_COLLECT_CAP) {
        matched.push(expandShardBill(bill));
      }
    }
  }

  matched.sort((a, b) => {
    const da = (a.latest_action_date || "").slice(0, 10);
    const db = (b.latest_action_date || "").slice(0, 10);
    return db.localeCompare(da);
  });

  return {
    total,
    results: matched.slice(offset, offset + limit),
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/api/health") {
      try {
        const object = await env.BUCKET.head("home_feed.json");
        const shards = await env.BUCKET.head("search_shards/meta.json");
        return jsonResponse(request, {
          ok: true,
          r2: object
            ? {
                key: "home_feed.json",
                size: object.size,
                uploaded: object.uploaded.toISOString(),
              }
            : null,
          search_shards: shards
            ? {
                key: "search_shards/meta.json",
                size: shards.size,
                uploaded: shards.uploaded.toISOString(),
              }
            : null,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResponse(request, { ok: false, error: message }, 500);
      }
    }

    if (request.method === "GET" && url.pathname === "/api/search") {
      const q = (url.searchParams.get("q") || "").trim();
      const stateKey = normalizeStateParam(url.searchParams.get("state") || "");
      const limit = clampInt(url.searchParams.get("limit"), DEFAULT_LIMIT, 1, MAX_LIMIT);
      const offset = clampInt(url.searchParams.get("offset"), 0, 0, 100_000);

      const fromParsed = parseOptionalDateParam(url.searchParams.get("date_from"));
      const toParsed = parseOptionalDateParam(url.searchParams.get("date_to"));
      if (fromParsed.error || toParsed.error) {
        return jsonResponse(
          request,
          {
            error: fromParsed.error || toParsed.error,
            results: [],
            total: 0,
            limit,
            offset,
          },
          400
        );
      }

      let dateFrom = fromParsed.date;
      let dateTo = toParsed.date;
      // If both provided and reversed, swap so the range is inclusive [min, max].
      if (dateFrom && dateTo && dateFrom > dateTo) {
        const tmp = dateFrom;
        dateFrom = dateTo;
        dateTo = tmp;
      }

      const hasDateFilter = Boolean(dateFrom || dateTo);
      // Text query is required unless browsing by date range only.
      if (q.length > 0 && q.length < MIN_QUERY_LEN) {
        return jsonResponse(
          request,
          {
            error: `Query must be at least ${MIN_QUERY_LEN} characters`,
            results: [],
            total: 0,
            limit,
            offset,
          },
          400
        );
      }
      if (!q && !hasDateFilter) {
        return jsonResponse(
          request,
          {
            error: `Provide a query of at least ${MIN_QUERY_LEN} characters, or date_from/date_to`,
            results: [],
            total: 0,
            limit,
            offset,
          },
          400
        );
      }

      try {
        const { results, total } = await searchBills(
          env,
          q,
          stateKey,
          limit,
          offset,
          dateFrom,
          dateTo
        );
        return jsonResponse(request, {
          results,
          total,
          limit,
          offset,
          q: q || null,
          state: stateKey || null,
          date_from: dateFrom,
          date_to: dateTo,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResponse(request, { error: message, results: [], total: 0, limit, offset }, 500);
      }
    }

    return jsonResponse(request, { error: "Not found" }, 404);
  },
};
