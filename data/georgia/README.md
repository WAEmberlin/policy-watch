# Georgia Open States bulk exports

Historical Georgia legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Drop extracted Open States bulk export folders here before importing.

## Import into PolicyWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/ga/`:

```bash
python src/processing/import_openstates_bulk.py --states ga
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
```

Raw export folders in this directory are gitignored (like `data/historic/` and `data/iowa/`). Large bill caches under `data/openstates/ga/` are also gitignored and live on Cloudflare R2 after upload.

## Publish to the live site (R2)

Georgia bills do not appear on [policywatch.us](https://policywatch.us) until the merged normalized corpus and docs are uploaded to Cloudflare R2. GitHub Actions cannot import bulk exports from this folder (gitignored).

**Option A — local upload** (R2 env vars required):

```bash
python src/processing/r2_sync.py rebuild-home-feeds
python src/processing/r2_sync.py upload
```

**Option B — GitHub Release + seed workflow** (recommended for ~10k bills):

Package Georgia with Kentucky (or re-run normalize after both imports), create a release, then run **Seed GA + KY cache to R2** (`.github/workflows/seed-ga-ky-r2.yml`):

```bash
python src/processing/import_openstates_bulk.py --states ga,ky
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
python scripts/package_ga_ky_r2_seed.py --output openstates-ga-ky.zip
gh release create openstates-ga-ky-YYYY-MM-DD openstates-ga-ky.zip
# Actions → Seed GA + KY cache to R2 → enter release tag
```

Georgia has no official PolicyWatch REST integration. Live updates use **Open States API v3**, merged on top of this bulk cache.
