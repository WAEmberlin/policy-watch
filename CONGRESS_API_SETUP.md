# Congress.gov API Setup Guide

This guide explains how to set up and use the Congress.gov API integration for fetching legislation data.

## Getting an API Key

1. Visit https://api.data.gov/signup/
2. Fill out the registration form:
   - Provide your email address
   - Describe your use case (e.g., "Policy tracking website")
   - Accept the terms of service
3. Check your email for the API key
4. The API key will look like: `your-api-key-here`

## Setting the API Key

### For Local Development

**Windows (PowerShell):**
```powershell
$env:CONGRESS_API_KEY = "your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set CONGRESS_API_KEY=your-api-key-here
```

**Linux/Mac:**
```bash
export CONGRESS_API_KEY=your-api-key-here
```

**Permanent Setup (Windows):**
1. Press `Win + X` → System → Advanced system settings
2. Click "Environment Variables"
3. Under "User variables", click "New"
4. Variable name: `CONGRESS_API_KEY`
5. Variable value: `your-api-key-here`
6. Click OK on all dialogs
7. Restart your terminal

**Permanent Setup (Linux/Mac):**
Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export CONGRESS_API_KEY=your-api-key-here
```

### For GitHub Actions

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `CONGRESS_API_KEY`
5. Value: `your-api-key-here`
6. Click **Add secret**

The workflow will automatically use this secret when running.

## Running the Script

### Manual Execution

```bash
python src/processing/fetch_congress_api.py
```

This will:
- Fetch all bills from the 119th Congress
- Handle pagination automatically
- Save results to `src/output/legislation.json`
- Deduplicate existing bills

### Automatic Execution

The script runs automatically as part of the daily GitHub Actions workflow:
- Runs daily at 23:30 UTC
- Can be manually triggered from the Actions tab
- Fetches new bills and updates existing ones

## How Pagination Works

The Congress.gov API returns up to 250 items per page. The script:

1. Starts at offset 0 (first page)
2. Fetches each page sequentially
3. Processes all bills on each page
4. Checks the total count to determine if more pages exist
5. Continues until all bills are fetched
6. Adds a small delay (100ms) between requests to respect rate limits

**Rate Limits:**
- API allows 1000 requests per hour
- Script includes delays to stay within limits
- If rate limited, script waits 60 seconds and retries

## Changing Congress Number

To fetch bills from a different Congress, edit `src/processing/fetch_congress_api.py`:

```python
CONGRESS_NUMBER = 120  # Change to desired Congress number
```

Common Congress numbers:
- 119th Congress: 2025-2026
- 118th Congress: 2023-2024
- 120th Congress: 2027-2028 (future)

After changing, run the script again to fetch bills from the new Congress.

## Data Structure

Each bill includes:
- `bill_number`: Bill number (e.g., "1234")
- `bill_type`: Type of bill (e.g., "HR", "S", "HJRES")
- `title`: Full bill title
- `summary`: Bill summary (if available)
- `sponsor_name`: Primary sponsor's name
- `latest_action`: Most recent action text
- `latest_action_date`: Date of latest action
- `url`: Link to bill on Congress.gov
- `published`: Publication/introduction date
- `congress`: Congress number

## Troubleshooting

### "CONGRESS_API_KEY environment variable not set"
- Make sure you've set the environment variable (see above)
- Restart your terminal after setting it
- Verify with: `echo $CONGRESS_API_KEY` (Linux/Mac) or `echo %CONGRESS_API_KEY%` (Windows)

### "API key may be invalid or missing permissions"
- Verify your API key is correct
- Check that you've activated your API key via email
- Try regenerating the key at https://api.data.gov/

### "Rate limit exceeded"
- The script will automatically wait 60 seconds and retry
- If this happens frequently, the script may need longer delays
- Consider running the script less frequently

### No bills fetched
- Check that the Congress number is valid
- Verify the API is responding: https://api.congress.gov/v3/bill/119?api_key=YOUR_KEY
- Check the script output for error messages

## Viewing Legislation

After running the script and `summarize.py`, legislation will appear on the website:
1. Click the "Legislation" tab
2. Use the search box to filter by title, summary, or sponsor
3. Use the bill type dropdown to filter by type (HR, S, etc.)
4. Click "View on Congress.gov" to see the full bill

