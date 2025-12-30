# ElevenLabs API 401 Unauthorized Error - Troubleshooting

If you're getting a `401 Client Error: Unauthorized` when generating audio, here's how to fix it:

## Common Causes

### 1. API Key Not Set (Local Testing)

If running locally, make sure the environment variable is set:

**Windows PowerShell:**
```powershell
$env:ELEVENLABS_API_KEY="your_actual_api_key_here"
python -m src.processing.weekly_overview
```

**Windows Command Prompt:**
```cmd
set ELEVENLABS_API_KEY=your_actual_api_key_here
python -m src.processing.weekly_overview
```

**Linux/Mac:**
```bash
export ELEVENLABS_API_KEY="your_actual_api_key_here"
python -m src.processing.weekly_overview
```

### 2. Invalid API Key

- **Check the key is correct**: Copy it directly from ElevenLabs (no extra spaces)
- **Verify it's active**: Log into https://elevenlabs.io and check your API keys
- **Check for typos**: Make sure there are no extra characters or spaces

### 3. API Key Format Issues

The API key should:
- Start with a letter/number (not a space or quote)
- Be about 30-50 characters long
- Not have quotes around it (unless using export in bash)

**Wrong:**
```bash
export ELEVENLABS_API_KEY="'sk-1234...'"  # Extra quotes
export ELEVENLABS_API_KEY=" sk-1234..."   # Leading space
```

**Correct:**
```bash
export ELEVENLABS_API_KEY="sk-1234..."     # Just the key
```

### 4. GitHub Actions Secret Not Set

If running in GitHub Actions:

1. **Check the secret exists**:
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Look for `ELEVENLABS_API_KEY`
   - If missing, add it (see `ELEVENLABS_SETUP.md`)

2. **Check the secret name**:
   - Must be exactly: `ELEVENLABS_API_KEY` (case-sensitive)
   - No spaces, no typos

3. **Check the secret value**:
   - Copy the API key directly from ElevenLabs
   - Paste it into the secret value field
   - No extra spaces before/after

### 5. API Key Permissions

Make sure your API key has:
- Text-to-speech permissions enabled
- Not expired or revoked
- Sufficient character quota (free tier: 10,000 chars/month)

### 6. Account Issues

- **Free tier limits**: Check if you've exceeded your monthly character limit
- **Account status**: Verify your ElevenLabs account is active
- **API access**: Some accounts may need to enable API access

## Testing Your API Key

You can test your API key directly with curl:

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" \
  -H "Accept: audio/mpeg" \
  -H "Content-Type: application/json" \
  -H "xi-api-key: YOUR_API_KEY_HERE" \
  -d '{
    "text": "Hello, this is a test.",
    "model_id": "eleven_monolingual_v1"
  }' \
  --output test.mp3
```

If this works, the API key is valid. If you get 401, the key is wrong.

## Getting a New API Key

1. Go to https://elevenlabs.io
2. Log in to your account
3. Go to Profile/Settings → API Keys
4. Generate a new API key
5. Copy it immediately (you won't see it again)
6. Update your environment variable or GitHub secret

## Quick Checklist

- [ ] API key is set as environment variable (local) or GitHub secret (Actions)
- [ ] API key name is exactly `ELEVENLABS_API_KEY` (case-sensitive)
- [ ] API key value has no extra spaces or quotes
- [ ] API key is active in your ElevenLabs account
- [ ] Account has not exceeded character limit
- [ ] API key has text-to-speech permissions

## Still Not Working?

1. **Check the error message**: The updated code now provides more specific error messages
2. **Verify locally first**: Test with environment variable before using GitHub Actions
3. **Check ElevenLabs dashboard**: Look for any account warnings or limits
4. **Try a new API key**: Generate a fresh key and try again

## Note

The weekly overview will still work without audio - it just won't generate the MP3 file. The text summary and JSON metadata will still be created successfully.


