# PolicyWatch API

Developer documentation for the **policywatch-api** Cloudflare Worker — a small read-only JSON API over legislative search data stored in Cloudflare R2.

Source: [`workers/policywatch-api/src/index.ts`](../workers/policywatch-api/src/index.ts)

---

## Overview

| | |
|---|---|
| **Base URL (production)** | `https://policywatch-api.wesley-a-emberlin.workers.dev` |
| **Auth** | None — endpoints are public (CORS-restricted for browser clients) |
| **Content type** | `application/json; charset=utf-8` |
| **Methods** | `GET`, `OPTIONS` (CORS preflight) |
| **R2 binding** | `BUCKET` → bucket `civicwatch-data` |

The Worker does not serve the full site JSON. Large feeds (`home_feed.json`, etc.) are loaded by the browser directly from the public R2 URL. This API exists for **bill search** (and a **health** check) so the Worker never has to hold the entire ~78MB search corpus in memory.

Optional future custom domain: `https://api.policywatch.us` (not configured yet). Point DNS / Workers custom domain at the same Worker when ready; clients should keep using `POLICYWATCH_API_BASE` so the base URL is easy to swap.

---

## Authentication

No API keys, tokens, or signed requests. Anyone can call the endpoints.

Browser clients are limited by CORS (see below). Non-browser clients (curl, server-side) can call the API without an `Origin` header; responses simply omit `Access-Control-Allow-Origin` in that case.

---

## CORS

Allowed origins (exact match):

- `https://policywatch.us`
- `https://www.policywatch.us`
- `https://waemberlin.github.io`

Also allowed for local development:

- `http://localhost` (any port)
- `http://127.0.0.1` (any port)

CORS response headers (when the request `Origin` is allowed):

| Header | Value |
|--------|--------|
| `Access-Control-Allow-Origin` | Echoed request origin |
| `Access-Control-Allow-Methods` | `GET, OPTIONS` |
| `Access-Control-Allow-Headers` | `Content-Type` |
| `Access-Control-Max-Age` | `86400` |
| `Vary` | `Origin` |

`OPTIONS` preflight returns **204** with the CORS headers above and an empty body.

---

## Endpoints

### `GET /api/health`

R2 connectivity check. Heads two objects in the bound bucket; does not download shard bodies.

#### Response `200`

```json
{
  "ok": true,
  "r2": {
    "key": "home_feed.json",
    "size": 1234567,
    "uploaded": "2026-08-08T12:00:00.000Z"
  },
  "search_shards": {
    "key": "search_shards/meta.json",
    "size": 1234,
    "uploaded": "2026-08-08T12:00:00.000Z"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `boolean` | `true` when the health handler completed without throwing |
| `r2` | `object \| null` | Head metadata for `home_feed.json`, or `null` if missing |
| `r2.key` | `string` | Always `"home_feed.json"` when present |
| `r2.size` | `number` | Object size in bytes |
| `r2.uploaded` | `string` | ISO-8601 upload timestamp |
| `search_shards` | `object \| null` | Head metadata for `search_shards/meta.json`, or `null` if missing |

#### Response `500`

Returned if the R2 binding throws (e.g. misconfigured binding):

```json
{
  "ok": false,
  "error": "…"
}
```

#### Example

```bash
curl -sS "https://policywatch-api.wesley-a-emberlin.workers.dev/api/health"
```

Example response:

```json
{
  "ok": true,
  "r2": {
    "key": "home_feed.json",
    "size": 4521891,
    "uploaded": "2026-08-08T18:22:11.000Z"
  },
  "search_shards": {
    "key": "search_shards/meta.json",
    "size": 512,
    "uploaded": "2026-08-08T18:22:11.000Z"
  }
}
```

---

### `GET /api/search`

Full-text substring search over bill shards in R2 (`search_shards/*.json`). Matching is case-insensitive against concatenated **title**, **bill number**, and **latest action** text.

Results are sorted by `latest_action_date` descending (date portion `YYYY-MM-DD`), then paginated with `offset` / `limit`.

#### Query parameters

| Param | Required | Default | Limits | Description |
|-------|----------|---------|--------|-------------|
| `q` | **Yes** | — | Min length **3** | Search query (trimmed). Shorter queries return **400**. |
| `state` | No | (all) | — | Jurisdiction filter. Empty = all shards. See [State filter](#state-filter). |
| `limit` | No | `25` | Clamped to **1–50** | Page size. |
| `offset` | No | `0` | Clamped to **0–100000** | Skip this many matches after sort. |

Invalid or non-numeric `limit` / `offset` fall back to the defaults above, then are clamped.

#### State filter

| Input | Normalized | Behavior |
|-------|------------|----------|
| *(omitted / empty)* | — | Search all shards listed in `search_shards/meta.json` |
| `KS`, `ks`, etc. | Uppercase (`KS`) | Prefer that shard key if present in meta; still apply per-bill state match |
| `federal` or `US` / `us` | `US` | Federal bills: `level === "federal"`, or empty/`US` state |

When `state` is set and equals a shard name in meta, only that shard is loaded. Otherwise every shard in meta is scanned (still applying the per-bill state filter).

#### Response `200`

```json
{
  "results": [
    {
      "bill_number": "HB 1234",
      "title": "Example bill title",
      "state": "KS",
      "level": "state",
      "latest_action": "Passed House",
      "latest_action_date": "2026-03-15",
      "url": "https://example.gov/bills/hb1234",
      "item_type": "bill_update",
      "action_type": ""
    }
  ],
  "total": 42,
  "limit": 25,
  "offset": 0,
  "q": "veteran",
  "state": "KS"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results` | `SearchBill[]` | Page of matches (see schema below) |
| `total` | `number` | Total matches across scanned shards (not capped by `limit`) |
| `limit` | `number` | Effective page size after clamping |
| `offset` | `number` | Effective offset after clamping |
| `q` | `string` | Trimmed query as received |
| `state` | `string \| null` | Normalized state key, or `null` if no state filter |

##### `SearchBill` schema

| Field | Type | Notes |
|-------|------|--------|
| `bill_number` | `string` | From shard `n` / `bill_number` |
| `title` | `string` | From shard `t` / `title` |
| `state` | `string` | From shard `s` / `state` |
| `level` | `string` | e.g. `"state"`, `"federal"` |
| `latest_action` | `string` | From shard `a` / `latest_action` |
| `latest_action_date` | `string` | From shard `d` / `latest_action_date` |
| `url` | `string` | From shard `u` / `url` |
| `item_type` | `string` | Always `"bill_update"` |
| `action_type` | `string` | Always `""` |

#### Response `400`

Query shorter than 3 characters:

```json
{
  "error": "Query must be at least 3 characters",
  "results": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

#### Response `500`

R2 / shard load failure (missing meta, empty shard list, missing shard file, etc.):

```json
{
  "error": "search_shards/meta.json missing from R2",
  "results": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

`limit` / `offset` in the 500 body reflect the clamped request values.

#### Examples

```bash
# Basic search
curl -sS "https://policywatch-api.wesley-a-emberlin.workers.dev/api/search?q=veteran"

# State + pagination
curl -sS "https://policywatch-api.wesley-a-emberlin.workers.dev/api/search?q=housing&state=KS&limit=10&offset=0"

# Federal
curl -sS "https://policywatch-api.wesley-a-emberlin.workers.dev/api/search?q=VA&state=federal"
```

Example `200` response (abbreviated):

```json
{
  "results": [
    {
      "bill_number": "SB 42",
      "title": "Veterans housing assistance",
      "state": "KS",
      "level": "state",
      "latest_action": "Referred to committee",
      "latest_action_date": "2026-02-10",
      "url": "https://www.kslegislature.gov/…",
      "item_type": "bill_update",
      "action_type": ""
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0,
  "q": "veteran",
  "state": "KS"
}
```

Example `400` (query too short):

```bash
curl -sS -i "https://policywatch-api.wesley-a-emberlin.workers.dev/api/search?q=va"
```

```json
{
  "error": "Query must be at least 3 characters",
  "results": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

---

### Unknown routes

Any other path (or non-GET/OPTIONS method that does not match the handlers) returns:

```json
{
  "error": "Not found"
}
```

Status **404**. CORS headers are still applied when the origin is allowed.

---

## Data source (R2)

| Binding | Bucket | Config |
|---------|--------|--------|
| `BUCKET` | `civicwatch-data` | [`workers/policywatch-api/wrangler.toml`](../workers/policywatch-api/wrangler.toml) |

Search reads compact per-jurisdiction shards rather than a single monolith:

| Key | Role |
|-----|------|
| `search_shards/meta.json` | `{ "shards": ["KS", "US", …], "bill_count"?, "generated_at"? }` |
| `search_shards/{KEY}.json` | Array of bills, or `{ "bills": […] }` — compact keys `n/t/s/l/a/d/u` or expanded field names |
| `home_feed.json` | Used only by `/api/health` (head check) |

Shards are produced by the site data pipeline and uploaded with other R2 artifacts. The largest shard is on the order of Massachusetts (~12–15MB compact).

---

## Rate and performance notes

| Constant | Value | Effect |
|----------|-------|--------|
| `MIN_QUERY_LEN` | `3` | Rejects shorter `q` with 400 |
| `DEFAULT_LIMIT` | `25` | Default page size |
| `MAX_LIMIT` | `50` | Hard cap on `limit` |
| `MATCH_COLLECT_CAP` | `2000` | Max matches kept in memory for sorting/paging; `total` still counts all matches |
| `CACHE_TTL_MS` | 10 minutes | In-isolate cache for meta + the last loaded shard |

**Shard loading**

- Meta and shard JSON are cached in Worker module scope with a 10-minute TTL.
- Only **one** shard body is kept parsed at a time (`shardCache.clear()` before storing the next) to avoid OOM from loading the full corpus (~78MB `home_search_bills.json`).
- Cold searches that span all jurisdictions load shards **sequentially**.
- A state-scoped search that matches a meta shard key loads a single file and is much cheaper.

There is **no application-level rate limit** in the Worker today. Cloudflare platform limits still apply. Prefer reasonable `limit` values and avoid hammering unfiltered all-shard queries.

---

## How the site uses the API

[`docs/data-config.js`](data-config.js) (generated/updated by CI via `src/processing/r2_sync.py`) sets:

```js
window.POLICYWATCH_API_BASE = 'https://policywatch-api.wesley-a-emberlin.workers.dev';
```

Homepage search in [`docs/script.js`](script.js) calls:

```text
GET {POLICYWATCH_API_BASE}/api/search?q=…&state=…&limit=…
```

and maps each result into the UI search result shape (`mapApiBillToSearchResult`). Override `POLICYWATCH_API_BASE` locally (or via the env used by R2 sync) to point the site at a different Worker URL.

---

## Local development

```bash
cd workers/policywatch-api
npm install
npx wrangler login   # once
npx wrangler dev --remote
```

`--remote` uses the real `civicwatch-data` R2 bucket via the binding in `wrangler.toml`. Wrangler prints a local URL (typically `http://127.0.0.1:8787`).

```bash
curl -sS "http://127.0.0.1:8787/api/health"
curl -sS "http://127.0.0.1:8787/api/search?q=veteran&state=KS"
```

For browser testing against the local Worker, serve the site from `http://localhost` / `http://127.0.0.1` (CORS allows those origins) and temporarily set `POLICYWATCH_API_BASE` to the Wrangler URL.

---

## Deploy

```bash
cd workers/policywatch-api
npx wrangler deploy
```

Requires Cloudflare auth with permission to deploy the `policywatch-api` Worker and access the `civicwatch-data` R2 bucket.

---

## Error summary

| Status | When |
|--------|------|
| **204** | `OPTIONS` CORS preflight |
| **200** | Successful health or search |
| **400** | Search `q` shorter than 3 characters |
| **404** | Unknown path |
| **500** | R2 / shard errors (health or search) |

All JSON error bodies include an `error` string (except health `500`, which uses `{ ok: false, error }`). Search errors also include empty `results` and `total: 0`.
