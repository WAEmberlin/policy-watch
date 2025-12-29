# Federal Hearings - API Limitation

## Current Status

The Congress.gov API v3 **does not appear to have a direct hearings endpoint** that we can use to fetch upcoming House and Senate committee hearings.

## Error Encountered

When attempting to fetch hearings, we get:
```
404 Client Error: Not Found for url: 
https://api.congress.gov/v3/committee/house/119/hearings
https://api.congress.gov/v3/committee/senate/119/hearings
```

## What This Means

- **Federal hearings cannot be fetched** through the current API structure
- The code will gracefully skip federal hearings fetching
- **State hearings (Kansas)** will continue to work normally
- The hearings page will show only state hearings for now

## Possible Solutions

### Option 1: Use Congress.gov RSS Feeds
Congress.gov may provide RSS feeds for committee hearings:
- Check for House committee RSS feeds
- Check for Senate committee RSS feeds
- Similar to how we fetch Kansas Legislature feeds

### Option 2: Scrape Committee Pages
- Not recommended (against constraints)
- Would require HTML parsing
- More fragile and error-prone

### Option 3: Use Different API Version
- Check if Congress.gov has a different API version with hearings support
- May require different authentication or endpoints

### Option 4: Manual Entry
- Add federal hearings manually if needed
- Or use a different data source

## Current Implementation

The code has been updated to:
- ✅ Gracefully handle missing hearings endpoint
- ✅ Continue working even if hearings can't be fetched
- ✅ Log clear messages about the limitation
- ✅ Not fail the entire workflow if hearings fail

## Next Steps

1. **Research Congress.gov API documentation** for hearings endpoints
2. **Check for RSS feeds** for House/Senate committee hearings
3. **Consider alternative data sources** for federal hearings
4. **For now**: Federal hearings feature is disabled, state hearings work normally

## State Hearings Still Work

Kansas Legislature conference committee hearings are working perfectly:
- ✅ Fetched from RSS feeds
- ✅ Displayed on hearings page
- ✅ Grouped by date with times
- ✅ Marked as "State (Kansas Legislature)"

The hearings page will continue to work with state hearings only until we find a way to fetch federal hearings.

