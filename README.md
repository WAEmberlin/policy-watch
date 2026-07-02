# CivicWatch (policy-watch)

**CivicWatch** is an open-source legislative tracking dashboard for veterans, military families, and civic engagement. It aggregates bill activity, hearings, live streams, and legislator data across **Kansas, Colorado, Arizona, Utah, Maine**, and **U.S. Congress**, with automated daily updates via GitHub Actions.

**Live site:** [https://waemberlin.github.io/policy-watch/](https://waemberlin.github.io/policy-watch/)

---

## What it does

- **Homepage feed** — Unified timeline of federal and state legislative activity, searchable and filterable by state, source, and topic.
- **Veterans & military impact matrix** — Bills tagged **Red** (high impact), **Yellow** (moderate), or **Green** (ceremonial/general) with colored cards and dedicated filters. See [docs/veterans-impact.html](docs/veterans-impact.html) on the live site.
- **Hearings calendar** — Upcoming and historical committee hearings with state/committee filters.
- **Live streams** — YouTube and official stream links for legislatures and Congress, with live-status detection.
- **District map** — Interactive Leaflet map of state legislative districts and U.S. House/Senate delegation for all tracked states.
- **Roll-call votes (Kansas)** — Yea/nay breakdowns with legislator profile links for supported KS bills.
- **Email digests** — Scheduled HTML email summaries of recent legislative activity.
- **Weekly AI overview** — Optional narrated weekly recap (ElevenLabs) generated on Fridays.

---

## Tech stack

| Layer | Technologies |
|-------|----------------|
| **Frontend** | Static HTML, vanilla JavaScript (IIFE modules), [Tailwind CSS](https://tailwindcss.com/) (CDN), custom CSS design tokens (`theme.css`) |
| **Maps** | [Leaflet](https://leafletjs.com/) + GeoJSON district boundaries |
| **Live streams page** | [Bootstrap 5](https://getbootstrap.com/) |
| **Hosting** | [GitHub Pages](https://pages.github.com/) — site served from `/docs` |
| **Data pipeline** | **Python 3.11** — fetch, normalize, enrich, summarize |
| **Data storage** | JSON files in `data/` and generated `docs/site_data.json` |
| **Configuration** | YAML (`config/states.yaml`, `config/livestreams.yaml`) |
| **APIs & feeds** | [Open States](https://openstates.org/), [Congress.gov API](https://api.congress.gov/), Kansas Legislature REST API, RSS/Atom feeds, [Cactus Watch](https://api.cactus.watch) (Arizona), Utah committee RSS, YouTube |
| **CI/CD** | GitHub Actions (`.github/workflows/`) — hourly data refresh, Open States sync, tests |
| **Testing** | [pytest](https://pytest.org/) |
| **Email** | Python `send_email.py` (SMTP) via scheduled workflow |
| **Optional AI/audio** | ElevenLabs API for weekly overview narration |

### Python dependencies

See [`requirements.txt`](requirements.txt): `feedparser`, `pyyaml`, `requests`, `beautifulsoup4`, `pytest`.

---

## Repository layout

```
policy-watch/
├── docs/                  # GitHub Pages site (HTML, JS, generated site_data.json)
├── src/processing/        # Python ETL: fetch, normalize, summarize, email
├── src/adapters/          # Data source adapters (Open States, Congress)
├── data/                  # Raw & normalized legislative JSON, GeoJSON, veterans tracker
├── config/                # State and livestream configuration
├── scripts/               # One-off import and maintenance scripts
├── tests/                 # pytest suite
└── .github/workflows/     # CI: daily update, Open States sync, tests, email
```

---

## Key data flows

1. **Fetch** — RSS feeds, Kansas API, Congress.gov, Open States bulk/sync, YouTube live status.
2. **Normalize** — Merge into unified bill/event records (`src/processing/normalize_data.py`).
3. **Enrich** — Kansas API details, AI topics (optional), veteran impact classification (`veteran_impact.py`).
4. **Summarize** — Build `docs/site_data.json`, weekly overview, email digest HTML.
5. **Deploy** — GitHub Actions commits updated `docs/` artifacts; Pages serves automatically.

### Veteran impact classification

All tracked states (including Colorado) and federal bills use keyword rules in `src/processing/veteran_impact.py` (benefits → Red, employment/courts → Yellow, memorials → Green), applied to Open States and feed bill text.

### Supplemental state sources (outside Open States)

| State | Source | Script | Output |
|-------|--------|--------|--------|
| **KS** | Official RSS + REST API | `fetch_kansas_rss.py`, `enrich_kansas_api.py` | `history.json`, `data/kansas/` |
| **AZ** | [Cactus Watch API](https://api.cactus.watch/api/bills) | `fetch_arizona_cactus.py` | `data/arizona/enrichments.json`, `history.json` |
| **UT** | Committee RSS (`le.utah.gov`) | `fetch_utah_committee_rss.py` | `data/utah/committee_hearings.json`, `history.json` |

Config: `config/state_feeds.yaml`

---

## Local development

### Prerequisites

- Python 3.11+
- Git

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

Serve the `docs/` folder with any static file server, e.g.:

```bash
python -m http.server 8080 --directory docs
```

Then open `http://localhost:8080/index.html`.

---

## GitHub Actions secrets (optional)

| Secret | Purpose |
|--------|---------|
| `KANSAS_LEGISLATURE_API_KEY` | Kansas bill enrichment & roll-call votes |
| `CONGRESS_API_KEY` | Congress.gov legislation & hearings |
| `ELEVENLABS_API_KEY` | Weekly overview audio narration |
| SMTP credentials | Email digest delivery (see `daily_email.yml`) |

Workflows degrade gracefully when secrets are not set.

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

---

## Contributing

Issues and pull requests are welcome. When changing data pipelines, run `pytest` and regenerate `docs/site_data.json` if schema or classification logic changes.

---

## License

See repository license file. Data from third-party APIs (Open States, Congress.gov, state legislatures) remains subject to those providers' terms.

---

## Disclaimer

CivicWatch is a civic information tool, not legal advice. Impact colors and summaries are automated aids — always consult official bill text and qualified counsel for decisions affecting benefits or rights.
