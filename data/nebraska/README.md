# Nebraska Open States bulk exports

Historical Nebraska legislative data exported from [Open States](https://openstates.org/) (JSON format 1.0).

Sessions included: 105, 106, 107, 107S1, 108, 108S1, 109.

## Import into CivicWatch

Bulk JSON is converted into the standard Open States cache at `data/openstates/ne/`:

```bash
python src/processing/import_openstates_bulk.py --states ne
python src/processing/normalize_data.py --skip-ai
python src/processing/summarize.py
```

Raw export folders in this directory are gitignored (like `data/historic/`). Commit the processed cache under `data/openstates/ne/` so CI and the site can use the historical data without re-importing ~100MB of source JSON.

The import runs automatically in CI before normalization when bulk files are present. Live API sync (`fetch_openstates.py`) merges on top of this cache on subsequent runs.
