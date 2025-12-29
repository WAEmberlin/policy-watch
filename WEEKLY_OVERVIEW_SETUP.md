# Weekly Overview Feature

The Weekly Overview feature generates a spoken-friendly summary of the last 7 days of activity from Congress, Kansas Legislature, and VA-related sources.

## Features

- **Automatic Generation**: Runs during the hourly GitHub Actions workflow
- **Multi-Source**: Combines data from Congress API, Kansas Legislature RSS, and VA feeds
- **Text-to-Speech**: Optional audio generation via ElevenLabs API
- **Frontend Display**: Automatically appears on the main page

## Output Files

The weekly overview generates the following files in `docs/weekly/`:

1. **`latest.json`**: Metadata including:
   - Week start/end dates
   - Item counts by category (Congress, Kansas, VA)
   - Generated script text
   - Audio availability status

2. **`weekly_overview.txt`**: Plain text version of the summary script

3. **`weekly_overview.mp3`**: Audio file (only if ElevenLabs API key is configured)

## Running Manually

To generate the weekly overview manually:

```bash
python -m src.processing.weekly_overview
```

Or:

```bash
python src/processing/weekly_overview.py
```

## How It Works

1. **Data Collection**: 
   - Loads items from `src/output/history.json` (RSS feeds, Kansas, VA)
   - Loads items from `src/output/legislation.json` (Congress bills)
   - Loads items from `src/output/federal_hearings.json` (Congress hearings)
   - Filters for items from the last 7 days

2. **Categorization**:
   - **Congress**: Items from Congress.gov API, federal hearings
   - **Kansas**: Items from Kansas Legislature RSS feeds
   - **VA**: Items from VA News or other veterans-related sources

3. **Summary Generation**:
   - Creates a neutral, factual summary (45-90 seconds when read)
   - Includes sample items from each category
   - Uses plain language suitable for text-to-speech

4. **Audio Generation** (if API key is set):
   - Sends script to ElevenLabs API
   - Uses professional, neutral voice
   - Saves as MP3 file

## Frontend Display

The weekly overview appears at the top of the main page (`docs/index.html`) in a dedicated section:

- **Week Range**: Shows the date range covered
- **Audio Player**: If audio is available, displays an HTML5 audio player
- **Summary Text**: Displays the full text of the weekly summary
- **Item Counts**: Shows counts for each category

If no weekly overview exists, the section is automatically hidden.

## Configuration

### ElevenLabs API Key

See `ELEVENLABS_SETUP.md` for detailed instructions on setting up the API key.

**Quick setup:**
1. Get API key from https://elevenlabs.io
2. Add as GitHub secret: `ELEVENLABS_API_KEY`
3. The workflow will automatically use it

### Voice Selection

The default voice is "Rachel" (ID: `21m00Tcm4TlvDq8ikWAM`), which is:
- Neutral and professional
- Available on free tier
- Good for news/informational content

To change the voice, edit `src/processing/weekly_overview.py` and update the voice ID in the `generate_audio()` function.

## Troubleshooting

### No Weekly Overview Appearing

1. **Check if files exist**:
   ```bash
   ls docs/weekly/
   ```

2. **Check GitHub Actions logs**:
   - Look for "Generate weekly overview" step
   - Check for any error messages

3. **Run manually**:
   ```bash
   python -m src.processing.weekly_overview
   ```

### Audio Not Generating

1. **Check API key is set** (see `ELEVENLABS_SETUP.md`)
2. **Check character limit** (free tier: 10,000 chars/month)
3. **Check error messages** in workflow logs

### Empty Summary

If the summary is empty or very short:
- Check if there are items in the last 7 days
- Verify data files exist (`history.json`, `legislation.json`)
- Check date filtering logic

## Customization

### Changing Summary Style

Edit the `generate_summary()` function in `src/processing/weekly_overview.py` to customize:
- Tone and style
- Structure and format
- Sample item selection
- Length and detail level

### Changing Time Range

To change from 7 days to a different period, modify the `timedelta(days=7)` in the `main()` function.

### Adding More Categories

1. Update `categorize_item()` to recognize new categories
2. Update `generate_summary()` to include new categories
3. Update frontend display if needed

## Integration with Workflow

The weekly overview is automatically generated during the hourly GitHub Actions workflow:

1. After fetching all data sources
2. After building the site data
3. Before sending emails
4. Committed along with other updates

The workflow will continue even if weekly overview generation fails (it's non-blocking).

