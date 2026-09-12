# Kentucky Open States bulk exports

Historical Kentucky legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Drop extracted Open States bulk export folders here before importing.

Kentucky’s Legislative Research Commission publishes the Legislative Record and a registered-user **Bill Watch** email tracker. There is no public REST or RSS bill API, so PolicyWatch uses **Open States** (same path as Iowa, Missouri, and Georgia).

## Import into PolicyWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/ky/`:

```bash
python src/processing/import_openstates_bulk.py --states ky
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
```

Raw export folders in this directory are gitignored (like `data/historic/` and `data/georgia/`). Large bill caches under `data/openstates/ky/` are also gitignored and live on Cloudflare R2 after upload.

## Publish to the live site (R2)

Same as Georgia — bulk caches are not in git; publish via R2. See [data/georgia/README.md](../georgia/README.md#publish-to-the-live-site-r2) for local upload or the **Seed GA + KY cache to R2** workflow (package both states together with `scripts/package_ga_ky_r2_seed.py`).

Live updates use **Open States API v3**, merged on top of this bulk cache.
