# Georgia Open States bulk exports

Historical Georgia legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Drop extracted Open States bulk export folders here before importing.

## Import into PolicyWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/ga/`:

```bash
python src/processing/import_openstates_bulk.py --states ga
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
python src/processing/r2_sync.py upload
```

Raw export folders in this directory are gitignored (like `data/historic/` and `data/iowa/`). Large bill caches under `data/openstates/ga/` are also gitignored and live on Cloudflare R2 after upload.

Georgia has no official PolicyWatch REST integration. Live updates use **Open States API v3**, merged on top of this bulk cache.
