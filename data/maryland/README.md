# Maryland Open States bulk exports

Historical Maryland legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Sessions included: 2023, 2024, 2025, 2026.

## Import into CivicWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/md/`:

```bash
python src/processing/import_openstates_bulk.py --states md
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
```

Raw export folders in this directory are gitignored (like `data/historic/`). Commit the processed cache under `data/openstates/md/` so CI and the site can use the historical data without re-importing source JSON.

Large states are stored as per-session files (`bills_2023.json`, `bills_2024.json`, …) when a single `bills.json` would exceed GitHub size limits.

Maryland has no official bill-tracking REST API. The Department of Legislative Services publishes RSS feeds for dashboards and publications only — CivicWatch uses **Open States API v3** for live updates, merged on top of this bulk cache.
