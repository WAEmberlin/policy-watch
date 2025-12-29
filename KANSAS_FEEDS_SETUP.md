# Kansas Legislature RSS Feeds Integration

This document explains how Kansas Legislature RSS feeds are integrated into CivicWatch.

## Feed Definitions

Kansas RSS feeds are defined in `src/processing/fetch_kansas_rss.py`:

- **House Actions**: `https://kslegislature.gov/li/rss/house_action.xml`
- **Senate Actions**: `https://kslegislature.gov/li/rss/senate_action.xml`
- **Committee Hearings**: `https://kslegislature.gov/li/rss/committee_hearings.xml`
- **Bill Introductions**: `https://kslegislature.gov/li/rss/bill_introductions.xml`

## Data Normalization

Each RSS item is normalized into a unified schema with these fields:

- `id`: Unique identifier (entry id or link)
- `title`: Item title
- `summary`: Item summary/description (truncated to 2000 chars)
- `link`: Link to original page
- `published`: ISO format date string
- `source`: "Kansas Legislature"
- `category`: One of "House", "Senate", "Committee", or "Bills"
- `type`: "state_legislation"
- `state`: "KS"
- `feed`: Internal feed key (house_actions, senate_actions, etc.)

## Integration Flow

1. **Fetch** (`fetch_kansas_rss.py`):
   - Fetches all 4 Kansas RSS feeds
   - Normalizes each item
   - Merges with existing history (deduplicates by id/link)
   - Saves to `src/output/history.json`

2. **Process** (`summarize.py`):
   - Loads items from `history.json`
   - Groups by Year → Date → Source
   - Kansas items are grouped as "Kansas Legislature - [Category]"
   - Includes in `docs/site_data.json`

3. **Display** (`docs/script.js`):
   - Shows Kansas items alongside other sources
   - Groups by date (newest first)
   - Filterable by source and category

## Deduplication

Items are deduplicated using:
- Primary: `id` field (from RSS entry)
- Fallback: `link` field (URL)

If an item with the same id or link already exists in history, it's not added again.

## Running the Update Process

### Manual Execution

```bash
# Fetch Kansas feeds
python src/processing/fetch_kansas_rss.py

# Regenerate site data
python src/processing/summarize.py
```

### Automatic Execution

The workflow runs automatically:
- Daily at 6:30 PM Central time
- Can be manually triggered from GitHub Actions

The workflow executes:
1. `fetch_feeds.py` (US Congress RSS, VA News)
2. `fetch_kansas_rss.py` (Kansas Legislature feeds)
3. `fetch_congress_api.py` (Congress.gov API bills)
4. `summarize.py` (combines everything)
5. Commits and pushes updates

## Adding More State RSS Feeds

To add RSS feeds from another state:

1. **Create a new module** (e.g., `src/processing/fetch_[state]_rss.py`):
   ```python
   STATE_FEEDS = {
       "feed_key": {
           "url": "https://...",
           "name": "State Name Legislature",
           "category": "Category",
           "feed_key": "feed_key"
       }
   }
   ```

2. **Use the same normalization schema**:
   - Follow the pattern in `fetch_kansas_rss.py`
   - Use `normalize_kansas_item()` as a template
   - Set `state` to the appropriate state code
   - Set `type` to "state_legislation"

3. **Integrate into workflow**:
   - Add step in `.github/workflows/daily.yml`:
     ```yaml
     - name: Fetch [State] RSS feeds
       run: python src/processing/fetch_[state]_rss.py
     ```

4. **Update frontend filters** (if needed):
   - Filters automatically populate from data
   - No code changes needed if using same schema

## Frontend Display

Kansas items appear:
- Grouped by date (newest first)
- Under source "Kansas Legislature - [Category]"
- Filterable by:
  - Source: "Kansas Legislature - House", etc.
  - Category: "House", "Senate", "Committee", "Bills"
- Searchable by title and summary
- Clickable links to original pages

## Troubleshooting

### No Kansas items appearing
- Check workflow logs for `fetch_kansas_rss.py` step
- Verify RSS feeds are accessible
- Check that items are being saved to `history.json`
- Ensure `summarize.py` is processing them

### Duplicate items
- Deduplication uses `id` and `link` fields
- If RSS feeds don't provide stable IDs, links are used
- Check that RSS entries have valid `id` or `link` fields

### Missing categories
- Categories come from feed definitions in `fetch_kansas_rss.py`
- Each feed has a `category` field (House, Senate, Committee, Bills)
- Frontend extracts categories from source names

