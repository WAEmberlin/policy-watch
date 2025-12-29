# Restoring VA News Data

## What Happened

When Kansas Legislature feeds were added, VA News data may have been lost due to:
1. The workflow running `fetch_kansas_rss.py` which might have had an issue preserving existing items
2. A potential deduplication conflict
3. The history file being overwritten incorrectly

## How to Restore VA News Data

### Option 1: Run Backfill Script (Recommended)

The backfill script will fetch VA News items from the RSS feed going back a specified number of days:

```bash
# Fetch last 30 days of VA News
python src/processing/backfill_history.py 30

# Or fetch last 90 days
python src/processing/backfill_history.py 90
```

This will:
- Fetch items from all feeds (including VA News)
- Add them to history.json
- Preserve existing items
- Deduplicate by link

### Option 2: Check Git History

If the data was lost recently, you might be able to restore from Git:

1. Check recent commits:
   ```bash
   git log --oneline --all -- src/output/history.json
   ```

2. Find a commit before Kansas feeds were added

3. Restore that version:
   ```bash
   git checkout <commit-hash> -- src/output/history.json
   ```

4. Then run the processing scripts again

### Option 3: Manual Re-fetch

1. Run `fetch_feeds.py` which will fetch VA News:
   ```bash
   python src/processing/fetch_feeds.py
   ```

2. This should add VA News items back to history.json

3. Then run `summarize.py` to regenerate site data:
   ```bash
   python src/processing/summarize.py
   ```

## Prevention

The updated `fetch_kansas_rss.py` now includes:
- Better preservation logic
- Safety checks to ensure no items are lost
- Error handling if history count drops unexpectedly

## Verify Restoration

After restoring, check:
1. `src/output/history.json` - should contain VA News items
2. Website - VA News items should appear in the feed
3. Search - should be able to find VA News items

## If Data is Still Missing

If VA News items are still missing after trying the above:

1. Check `src/output/history.json` directly:
   ```bash
   # Count items by source
   python -c "import json; data = json.load(open('src/output/history.json')); sources = {}; [sources.update({item.get('source', 'Unknown'): sources.get(item.get('source', 'Unknown'), 0) + 1}) for item in data]; print(sources)"
   ```

2. Check workflow logs in GitHub Actions to see what happened

3. The VA News RSS feed is: `https://news.va.gov/feed/`
   - You can verify it's working by visiting this URL

