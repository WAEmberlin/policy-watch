# ElevenLabs API Setup for Weekly Overview

This guide explains how to set up the ElevenLabs API key for generating audio narrations of the weekly overview.

## Overview

The weekly overview feature can optionally generate MP3 audio files using the ElevenLabs text-to-speech API. This is completely optional - if no API key is provided, the feature will work normally without audio.

## Getting an ElevenLabs API Key

1. **Sign up for ElevenLabs**:
   - Visit https://elevenlabs.io
   - Create a free account (free tier includes 10,000 characters per month)

2. **Get your API key**:
   - Log in to your ElevenLabs account
   - Go to your profile/settings
   - Find your API key (or generate a new one)
   - Copy the API key

## Setting Up the API Key

### For Local Development

Create a `.env` file in the project root (optional, for local testing):

```bash
ELEVENLABS_API_KEY=your_api_key_here
```

Or set it as an environment variable:

**Windows (PowerShell):**
```powershell
$env:ELEVENLABS_API_KEY="your_api_key_here"
```

**Windows (Command Prompt):**
```cmd
set ELEVENLABS_API_KEY=your_api_key_here
```

**Linux/Mac:**
```bash
export ELEVENLABS_API_KEY="your_api_key_here"
```

### For GitHub Actions

1. **Add the secret to GitHub**:
   - Go to your repository on GitHub (e.g., `https://github.com/yourusername/policy-watch`)
   - Click the **Settings** tab (at the top of the repository page)
   - In the left sidebar, click **Secrets and variables** → **Actions**
   - Click the **New repository secret** button (green button on the right)
   - **Name**: `ELEVENLABS_API_KEY` (must be exactly this, case-sensitive)
   - **Secret**: Paste your ElevenLabs API key here
   - Click **Add secret**

2. **The workflow will automatically use it**:
   The `.github/workflows/daily.yml` workflow is already configured to use this secret. No code changes needed.

**Note**: Once added, the secret value cannot be viewed again (for security), but you can update or delete it if needed.

## Running the Weekly Overview

### Manual Run

```bash
python -m src.processing.weekly_overview
```

Or:

```bash
python src/processing/weekly_overview.py
```

### Automatic Run

The weekly overview is automatically generated during the hourly GitHub Actions workflow. If the `ELEVENLABS_API_KEY` secret is set, audio will be generated. If not, the script will skip audio generation gracefully.

## Free Tier Limits

The ElevenLabs free tier includes:
- **10,000 characters per month**
- Access to standard voices
- MP3 output format

A typical weekly overview script is approximately 200-400 characters, so you can generate about 25-50 weekly overviews per month on the free tier.

## Troubleshooting

### Audio Not Generating

1. **Check API key is set**:
   ```bash
   echo $ELEVENLABS_API_KEY  # Linux/Mac
   echo %ELEVENLABS_API_KEY%  # Windows CMD
   $env:ELEVENLABS_API_KEY   # Windows PowerShell
   ```

2. **Check API key is valid**:
   - Verify the key in your ElevenLabs account
   - Make sure there are no extra spaces or quotes

3. **Check character limit**:
   - Log in to ElevenLabs and check your usage
   - Free tier resets monthly

4. **Check error messages**:
   - The script will print error messages if audio generation fails
   - Check GitHub Actions logs for detailed error information

### Audio File Not Appearing on Website

1. **Check file exists**:
   - Verify `docs/weekly/weekly_overview.mp3` exists
   - Check file size (should be > 0 bytes)

2. **Check GitHub Pages**:
   - The file needs to be committed and pushed to GitHub
   - GitHub Pages may take a few minutes to update

3. **Check browser console**:
   - Open browser developer tools (F12)
   - Check for 404 errors loading the audio file

## Testing Locally

To test the weekly overview generation locally:

1. **Set the API key** (see above)

2. **Run the script**:
   ```bash
   python -m src.processing.weekly_overview
   ```

3. **Check output**:
   - `docs/weekly/latest.json` - Metadata
   - `docs/weekly/weekly_overview.txt` - Text script
   - `docs/weekly/weekly_overview.mp3` - Audio (if API key is set)

4. **View on website**:
   - Open `docs/index.html` in a browser
   - The weekly overview section should appear at the top

## Disabling Audio Generation

If you want to disable audio generation:

1. **Remove the secret** (GitHub Actions):
   - Go to repository Settings → Secrets
   - Delete `ELEVENLABS_API_KEY`

2. **Or unset locally**:
   ```bash
   unset ELEVENLABS_API_KEY  # Linux/Mac
   set ELEVENLABS_API_KEY=   # Windows CMD
   ```

The script will continue to work normally, just without audio generation.

