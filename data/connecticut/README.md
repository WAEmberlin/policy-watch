# Connecticut Open States bulk exports

Historical Connecticut legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Drop extracted Open States bulk export folders here before importing.

Connecticut does not have a public REST bill API used by PolicyWatch, so ingest uses **Open States** (same path as Georgia, Kentucky, and Iowa).

## Import into PolicyWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/ct/`:

```bash
python src/processing/import_openstates_bulk.py --states ct
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
python src/processing/r2_sync.py upload
```

Raw export folders in this directory are gitignored. Large bill caches under `data/openstates/ct/` are also gitignored and live on Cloudflare R2 after upload.

Live updates use **Open States API v3**, merged on top of this bulk cache.
