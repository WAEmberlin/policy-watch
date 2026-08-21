# PolicyWatch (policy-watch)

**PolicyWatch** is an open-source multi-state + Congress legislative tracker for veterans, military families, and civic engagement. It aggregates bill activity, hearings, livestreams, district maps, elections links, and email digests — with **red / yellow / green** veteran-impact coloring and automated daily updates via GitHub Actions.

**Live site:** [https://policywatch.us](https://policywatch.us)  
Mirror: [https://waemberlin.github.io/policy-watch/](https://waemberlin.github.io/policy-watch/)

---

## What it does

- **Homepage feed** — Unified timeline of federal and state legislative activity, searchable and filterable by state, source, and topic.
- **Veterans & military impact matrix** — Bills tagged **Red** (high impact), **Yellow** (moderate), or **Green** (ceremonial/general) with colored cards and dedicated filters. See [docs/veterans-impact.html](docs/veterans-impact.html) on the live site.
- **Hearings calendar** — Upcoming and historical committee hearings with state/committee filters.
- **District map** — Interactive Leaflet map of state legislative districts and U.S. House/Senate delegation for tracked states.
- **Elections links** — Dashboard of official SOS / election calendar and results links by jurisdiction.
- **Live streams** — YouTube and official stream links for legislatures and Congress, with live-status detection.
- **Roll-call votes (Kansas + Open States)** — Yea/nay breakdowns with legislator profile links where available.
- **Email digests** — Scheduled HTML email summaries of recent legislative activity.
- **Weekly AI overview** — Optional narrated weekly recap (ElevenLabs) generated on Fridays.

---

## Tracked jurisdictions

| Code | Jurisdiction |
|------|--------------|
| Federal | U.S. Congress (House & Senate) |
| KS | Kansas |
| CO | Colorado |
| AZ | Arizona |
| UT | Utah |
| ME | Maine |
| NE | Nebraska |
| MD | Maryland |
| PA | Pennsylvania |
| MA | Massachusetts |
| WV | West Virginia |
| TN | Tennessee |
| NC | North Carolina |
| MO | Missouri |
| IA | Iowa |

Configured in [`config/states.yaml`](config/states.yaml).

---

## How the site works

```
GitHub Actions (fetch → normalize → summarize)
        │
        ├─► commit slim UI / lookups to /docs  ──► GitHub Pages (static site)
        │
        └─► upload large JSON to Cloudflare R2 (civicwatch-data)
                    │
                    ├─► browser loads home_feed, hearings, etc. from R2
                    └─► policywatch-api Worker (search / health) bound to same bucket
```

| Piece | Role |
|-------|------|
| **GitHub Pages** | Hosts the static UI from `/docs` (HTML, JS, CSS, small lookups). |
| **Cloudflare R2** | Holds large JSON: `home_feed.json`, `home_search_bills.json`, `legislators_directory.json`, `hearings.json`, Open States caches, full `site_data.json`, etc. Public base URL is set via `R2_PUBLIC_BASE_URL` / `docs/data-config.js`. |
| **Slim first paint** | Pages prefer slim artifacts (`home_feed`, `legislators_directory`, `hearings`) so mobile never parses a full ~100–200MB `site_data.json` on load. |
| **GitHub Actions** | Pipelines: daily update, Open States sync, summarize, R2 upload (see `.github/workflows/`). |
| **Cloudflare Worker** | [`policywatch-api`](workers/policywatch-api) — search/health API at [https://policywatch-api.wesley-a-emberlin.workers.dev](https://policywatch-api.wesley-a-emberlin.workers.dev), R2 binding `BUCKET` → bucket `civicwatch-data`. |

### API

Public developer docs for the Worker (endpoints, CORS, schemas, local/dev deploy): **[docs/API.md](docs/API.md)**.

Base URL: `https://policywatch-api.wesley-a-emberlin.workers.dev` (set as `POLICYWATCH_API_BASE` in [`docs/data-config.js`](docs/data-config.js)).

### Data pipeline (high level)

1. **Fetch** — RSS, Kansas API, Congress.gov, Open States sync, YouTube live status.
2. **Normalize** — Unified bill/event records (`src/processing/normalize_data.py`).
3. **Enrich** — Kansas API details, veteran impact classification (`veteran_impact.py`), optional AI topics.
4. **Summarize** — Build site artifacts; emit slim feeds for the homepage and directories.
5. **Deploy** — Commit UI/docs updates to GitHub Pages; upload heavy JSON to R2.

### Veteran impact classification

All tracked states and federal bills use keyword rules in `src/processing/veteran_impact.py` (benefits / VA healthcare / housing / disability → Red; employment, licensing, courts, mental health, military spouse → Yellow; recognition / memorials → Green). Colorado CSV impact levels override keyword rules when present.

### Supplemental state sources (outside Open States)

| State | Source | Script | Output |
|-------|--------|--------|--------|
| **KS** | Official RSS + REST API | `fetch_kansas_rss.py`, `enrich_kansas_api.py` | `history.json`, `data/kansas/` |
| **AZ** | [Cactus Watch API](https://api.cactus.watch/api/bills) | `fetch_arizona_cactus.py` | `data/arizona/enrichments.json`, `history.json` |
| **UT** | Committee RSS (`le.utah.gov`) | `fetch_utah_committee_rss.py` | `data/utah/committee_hearings.json`, `history.json` |

Config: `config/state_feeds.yaml`

---

## Tech stack

| Layer | Technologies |
|-------|----------------|
| **Frontend** | Static HTML, vanilla JavaScript, [Tailwind CSS](https://tailwindcss.com/) (CDN), `theme.css` |
| **Maps** | [Leaflet](https://leafletjs.com/) + GeoJSON |
| **Hosting** | GitHub Pages (`/docs`) + custom domain **policywatch.us** |
| **Object storage** | Cloudflare R2 (`civicwatch-data`) |
| **API** | Cloudflare Worker (`workers/policywatch-api`) |
| **Data pipeline** | Python 3.11 — fetch, normalize, enrich, summarize |
| **Configuration** | YAML (`config/states.yaml`, `config/livestreams.yaml`) |
| **APIs & feeds** | [Open States](https://openstates.org/), [Congress.gov](https://api.congress.gov/), Kansas Legislature REST, RSS/Atom, Cactus Watch (AZ), Utah committee RSS, YouTube |
| **CI/CD** | GitHub Actions — daily update, Open States sync, summarize, R2 upload, tests, email |
| **Testing** | [pytest](https://pytest.org/) |

Python deps: see [`requirements.txt`](requirements.txt).

---

## Repository layout

```
policy-watch/
├── docs/                      # GitHub Pages site (static UI)
├── workers/policywatch-api/   # Cloudflare Worker (R2-backed API)
├── src/processing/            # Python ETL: fetch, normalize, summarize, R2 sync
├── src/adapters/              # Data source adapters (Open States, Congress)
├── data/                      # Raw & normalized legislative JSON, GeoJSON
├── config/                    # State and livestream configuration
├── scripts/                   # One-off import / maintenance scripts
├── tests/                     # pytest suite
└── .github/workflows/         # daily, openstates, summarize, R2 upload, email, tests
```

---

## Local development

### Prerequisites

- Python 3.11+
- Git
- Node.js (for the Worker)

### Setup

```bash
git clone https://github.com/WAEmberlin/policy-watch.git
cd policy-watch
pip install -r requirements.txt
```

### Refresh site data

```bash
python src/processing/fetch_feeds.py
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
```

### Run tests

```bash
pytest
```

### Preview the site locally

```bash
python -m http.server 8080 --directory docs
```

Open `http://localhost:8080/index.html`. On localhost the UI loads JSON from the local `docs/` server (R2 CORS usually blocks `localhost`). Set `window.POLICYWATCH_FORCE_R2 = true` before `data-url.js` if you need the remote bucket instead.

### Worker (local)

```bash
cd workers/policywatch-api
npm install
npx wrangler dev --remote
```

Uses `wrangler login` and the R2 bucket binding in `wrangler.toml` (`civicwatch-data`). `--remote` talks to the real R2 bucket.

---

## Secrets / environment

### GitHub Actions (R2 upload & sync)

| Secret | Purpose |
|--------|---------|
| `R2_ACCOUNT_ID` | Cloudflare account ID for R2 S3 API |
| `R2_ACCESS_KEY_ID` | R2 API access key |
| `R2_SECRET_ACCESS_KEY` | R2 API secret key |
| `R2_BUCKET_NAME` | Bucket name (e.g. `civicwatch-data`) |
| `R2_PUBLIC_BASE_URL` | Public HTTPS base for browser fetches |

Used by daily / Open States / upload workflows via `src/processing/r2_sync.py`.

### Other optional secrets

| Secret | Purpose |
|--------|---------|
| `KANSAS_LEGISLATURE_API_KEY` | Kansas bill enrichment & roll-call votes |
| `CONGRESS_API_KEY` | Congress.gov legislation & hearings |
| `ELEVENLABS_API_KEY` | Weekly overview audio narration |
| SMTP credentials | Email digest delivery (see `daily_email.yml`) |

Workflows degrade gracefully when optional secrets are unset; R2 secrets are required for production data publish.

### Worker

Auth is via `wrangler login` (or CI deploy tokens). The Worker does **not** use the `R2_*` S3 secrets — it uses the R2 binding in `wrangler.toml` (`BUCKET` → `civicwatch-data`).

---

## Contributing

Issues and pull requests are welcome. When changing data pipelines, run `pytest` and regenerate site artifacts if schema or classification logic changes.

---

## License

See repository license file. Data from third-party APIs (Open States, Congress.gov, state legislatures) remains subject to those providers' terms.

---

## Disclaimer

PolicyWatch is a civic information tool, not legal advice. Impact colors and summaries are automated aids — always consult official bill text and qualified counsel for decisions affecting benefits or rights.
