# CivicWatch Updates Summary

This document summarizes the major changes made to transform Policy Watch into CivicWatch.

## 1. Email Schedule Update

**Changed**: Daily email time from 5:43 PM to 6:30 PM Central time

**File**: `.github/workflows/daily.yml`
- Updated cron schedule from `"30 23 * * *"` to `"30 0 * * *"` (00:30 UTC = 6:30 PM Central)
- Updated workflow name to "Daily CivicWatch Update"
- Updated commit message to "Automated daily CivicWatch update"

## 2. Site Rebranding to CivicWatch

**Changed**: Site name from "Policy Watch" to "CivicWatch"

**Files Modified**:
- `docs/index.html`: Updated title, added logo header, styled "Civic" and "Watch" text
- `.github/workflows/daily.yml`: Updated workflow and commit messages

**Logo Setup**:
- Place your logo image as `docs/logo.png`
- Logo will display at 60px height next to the site title
- If logo is missing, it will be hidden gracefully

## 3. Unified Date-Based Display

**Changed**: All items (RSS feeds, Congress bills, Kansas legislation) now display together by date

**Files Modified**:
- `docs/script.js`: Completely rewritten to show unified view
- Removed separate "RSS Feeds" and "Legislation" tabs
- All items grouped by: Year → Date → Source
- Items sorted newest first within each date

**Benefits**:
- Single view of all updates
- Easier to see what happened on a specific date
- Consistent display format

## 4. Source and Category Filters

**Added**: Filter dropdowns for Source and Category

**Files Modified**:
- `docs/index.html`: Added filter container with source and category dropdowns
- `docs/script.js`: Implemented filter logic

**Filter Options**:
- **Source Filter**: Filter by specific source (e.g., "Kansas Legislature - House", "VA News", "Congress.gov API")
- **Category Filter**: Filter by category (e.g., "House", "Senate", "Committee", "Bills")
- Filters work together (AND logic)
- "Clear Filters" button to reset

## 5. Kansas Legislature RSS Feeds Integration

**Added**: Support for 4 Kansas Legislature RSS feeds

**New File**: `src/processing/fetch_kansas_rss.py`
- Fetches House Actions, Senate Actions, Committee Hearings, and Bill Introductions
- Normalizes data into unified schema
- Deduplicates by id/link
- Merges with existing history

**Files Modified**:
- `.github/workflows/daily.yml`: Added step to fetch Kansas feeds
- `src/processing/fetch_feeds.py`: Removed old Kansas feed reference
- `src/processing/summarize.py`: Updated to handle Kansas categories in source names
- `docs/script.js`: Updated to display Kansas items with categories

**Kansas Feed URLs**:
- House Actions: `https://kslegislature.gov/li/rss/house_action.xml`
- Senate Actions: `https://kslegislature.gov/li/rss/senate_action.xml`
- Committee Hearings: `https://kslegislature.gov/li/rss/committee_hearings.xml`
- Bill Introductions: `https://kslegislature.gov/li/rss/bill_introductions.xml`

**Data Schema**:
Each Kansas item includes:
- `id`, `title`, `summary`, `link`, `published`
- `source`: "Kansas Legislature"
- `category`: "House", "Senate", "Committee", or "Bills"
- `type`: "state_legislation"
- `state`: "KS"
- `feed`: Internal feed identifier

## 6. Frontend Improvements

**Changes**:
- Unified display shows all items by date
- Search works across all sources (RSS feeds, Congress bills, Kansas legislation)
- Filters dynamically populate from available sources/categories
- Pagination works with filtered results
- Empty states show "No updates for this date/source"

## How to Use

### Adding the Logo

1. Save your logo image as `docs/logo.png`
2. The logo will automatically appear in the header
3. Supported formats: PNG, JPG, SVG (PNG recommended)

### Running Updates Manually

```bash
# Fetch all feeds
python src/processing/fetch_feeds.py
python src/processing/fetch_kansas_rss.py
python src/processing/fetch_congress_api.py  # Requires CONGRESS_API_KEY

# Generate site data
python src/processing/summarize.py
```

### Automatic Updates

The GitHub Actions workflow runs daily at 6:30 PM Central time and:
1. Fetches all RSS feeds (US Congress, VA News)
2. Fetches Kansas Legislature feeds
3. Fetches Congress.gov API bills (if API key is set)
4. Generates site data
5. Sends daily email
6. Commits and pushes updates

## File Structure

```
docs/
  ├── index.html          # Main HTML (updated with logo, filters)
  ├── script.js           # Frontend logic (unified view, filters)
  └── logo.png            # Logo image (you need to add this)

src/processing/
  ├── fetch_feeds.py      # US Congress RSS, VA News
  ├── fetch_kansas_rss.py # NEW: Kansas Legislature feeds
  ├── fetch_congress_api.py # Congress.gov API bills
  └── summarize.py        # Combines all data into site_data.json

.github/workflows/
  └── daily.yml           # Updated schedule and Kansas feed step
```

## Next Steps

1. **Add Logo**: Place `logo.png` in the `docs/` directory
2. **Test Locally**: Run the processing scripts and view `docs/index.html`
3. **Verify Workflow**: Check GitHub Actions runs successfully
4. **Monitor**: Check that Kansas feeds are being fetched and displayed

## Documentation

- `KANSAS_FEEDS_SETUP.md`: Detailed guide for Kansas feeds integration
- `CONGRESS_API_SETUP.md`: Guide for Congress.gov API setup (existing)

## Questions?

- Kansas feeds not appearing? Check `KANSAS_FEEDS_SETUP.md` troubleshooting section
- Logo not showing? Verify `docs/logo.png` exists and is a valid image
- Filters not working? Check browser console for JavaScript errors


