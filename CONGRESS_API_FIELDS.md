# Congress.gov API - All Available Fields

## Bill Data Fields

The Congress.gov API now extracts **all available fields** for each bill:

### Basic Information
- `bill_number` - Bill number (e.g., "6925")
- `bill_type` - Type of bill (HR, S, HJRES, etc.)
- `title` - Full bill title
- `summary` - Bill summary/description (truncated to 2000 chars)
- `congress` - Congress number (119)
- `url` - Congress.gov URL

### Sponsor Information
- `sponsor_name` - Primary sponsor's full name
- `sponsor_party` - Sponsor's party (D, R, I)
- `sponsor_state` - Sponsor's state
- `sponsor_district` - Sponsor's district (for House members)

### Cosponsors
- `cosponsors` - Array of cosponsor objects, each containing:
  - `name` - Cosponsor's full name
  - `party` - Cosponsor's party
  - `state` - Cosponsor's state

### Legislative Actions
- `latest_action` - Most recent action text
- `latest_action_date` - Date of latest action
- `actions` - Full chronological list of all actions, each containing:
  - `text` - Action description
  - `actionDate` - Date of action
  - `type` - Type of action

### Committee Information
- `committees` - Array of committee objects, each containing:
  - `name` - Committee name
  - `systemCode` - Committee system code

### Policy Areas & Subjects
- `policy_areas` - Array of policy area/subject names

### Status & Votes
- `status` - Current legislative status
- `votes` - Array of vote records, each containing:
  - `rollNumber` - Roll call number
  - `chamber` - Chamber (House/Senate)
  - `date` - Vote date
  - `result` - Vote result

### Dates
- `introduced_date` - When bill was introduced
- `published` - Publication date (used for sorting)

## Federal Hearings

The API now also fetches **federal hearings** from House and Senate committees:

### Hearing Fields
- `title` - Hearing title
- `scheduled_date` - Scheduled date (ISO format)
- `scheduled_time` - Scheduled time
- `location` - Hearing location
- `committee` - Committee name
- `chamber` - "House" or "Senate"
- `url` - Link to hearing details
- `source` - "Federal (US Congress)"
- `congress` - Congress number

### How It Works
1. Fetches House committee hearings
2. Fetches Senate committee hearings
3. Normalizes and saves to `src/output/federal_hearings.json`
4. Integrated into hearings page alongside state hearings

## Display on Website

### Bills
All bill fields are stored in `legislation.json` and available for display. Currently displayed:
- Bill number and type
- Title
- Summary
- Sponsor name
- Latest action
- Link to Congress.gov

**Additional fields available** (can be added to frontend):
- Cosponsors list
- Committee referrals
- Full actions history
- Policy areas
- Vote records

### Hearings
Hearings page displays:
- **State hearings** (Kansas Legislature) - marked with "State (Kansas Legislature)" badge
- **Federal hearings** (US Congress) - marked with "Federal (US Congress)" badge
- Grouped by date
- Time shown next to title
- Separate sections for upcoming and historical

## API Endpoints Used

- **Bills**: `https://api.congress.gov/v3/bill/{congress}`
- **House Hearings**: `https://api.congress.gov/v3/committee/house/{congress}/hearings`
- **Senate Hearings**: `https://api.congress.gov/v3/committee/senate/{congress}/hearings`

## Rate Limits

- 1000 requests per hour
- Small delay (0.1s) between requests to stay within limits
- Pagination handled automatically

## Files Modified

1. `src/processing/fetch_congress_api.py`
   - Updated `normalize_bill()` to extract all fields
   - Added `fetch_hearings()` function
   - Added `fetch_committee_hearings()` function
   - Added `normalize_hearing()` function
   - Updated `main()` to fetch and save hearings

2. `src/processing/summarize.py`
   - Loads federal hearings from `federal_hearings.json`
   - Combines state and federal hearings
   - Marks state hearings with source

3. `docs/hearings.html`
   - Displays source badge (State vs Federal)
   - Shows time next to title
   - Groups by date

## Next Steps

To display additional bill fields on the website:
1. Update `docs/script.js` to show cosponsors, committees, etc.
2. Add filters for policy areas
3. Display full actions history
4. Show vote records

All data is already being fetched and stored - just needs frontend display logic!

