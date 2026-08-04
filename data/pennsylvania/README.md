# Pennsylvania Open States bulk exports

Historical Pennsylvania legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Sessions included: 2021-2022, 2023-2024, 2023-2024S1, 2025-2026.

## Import into CivicWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/pa/`:

```bash
python src/processing/import_openstates_bulk.py --states pa
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
python src/processing/r2_sync.py upload
```

Raw export folders in this directory are gitignored (like `data/historic/` and `data/maryland/`). Large bill caches under `data/openstates/pa/` are also gitignored and live on Cloudflare R2 after upload.

Pennsylvania has no official CivicWatch REST integration. Live updates use **Open States API v3**, merged on top of this bulk cache.
