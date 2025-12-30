# Deployment Guide: Ollama Pipeline Integration

## The Problem

The map-reduce summarization pipeline requires Ollama running locally with GPU access. This creates a challenge:
- **GitHub Actions**: Runs in cloud, no GPU, no Ollama
- **Laptop Off**: When your laptop is off, Ollama isn't available
- **Website Needs**: The website needs summaries even when Ollama isn't running

## Solution: Hybrid Approach

We use a **hybrid approach** with graceful fallback:

1. **Base Summary** (always works): Uses existing `weekly_overview.py` logic
2. **Enhanced Summary** (optional): Uses Ollama when available
3. **Caching**: Pre-generated summaries can be committed to repo
4. **Fallback**: Website always has base summary, enhanced is bonus

## Architecture

```
┌─────────────────────────────────────────┐
│  GitHub Actions Workflow                │
│  (runs hourly, no GPU)                 │
└──────────────┬──────────────────────────┘
               │
               ├─> weekly_overview.py (always works)
               │   └─> Base summary (simple, fast)
               │
               └─> weekly_integration.py (optional)
                   ├─> Checks for Ollama
                   ├─> If available: Enhanced summaries
                   └─> If not: Falls back to base
```

## Deployment Options

### Option 1: Local Generation + Commit (Recommended)

**When laptop is on:**
1. Run enhanced pipeline locally
2. Commit generated summaries to repo
3. GitHub Actions uses cached summaries

```bash
# On your laptop (when it's on)
python civicwatch/weekly_integration.py

# Commit the results
git add civicwatch/storage/summaries/
git add docs/weekly/
git commit -m "Update weekly summaries"
git push
```

**Pros:**
- Works even when laptop is off (summaries in repo)
- No cloud GPU costs
- Full control over when summaries are generated

**Cons:**
- Requires manual/local generation
- Summaries may be slightly stale

### Option 2: Cloud GPU Service (Advanced)

Use a cloud service with GPU:
- **RunPod**: ~$0.20/hour for GPU instances
- **Vast.ai**: Cheap GPU rentals
- **Google Colab**: Free GPU (limited)

Set up a separate workflow that:
1. Spins up GPU instance
2. Runs Ollama + pipeline
3. Commits results
4. Shuts down instance

**Pros:**
- Fully automated
- Always up-to-date

**Cons:**
- Costs money (~$5-10/month)
- More complex setup

### Option 3: Hybrid (Current Implementation)

The `weekly_integration.py` script:
- Always generates base summary (works everywhere)
- Tries to enhance with Ollama if available
- Falls back gracefully if Ollama unavailable

**GitHub Actions workflow:**
```yaml
- name: Generate weekly overview (base)
  run: python -m src.processing.weekly_overview

- name: Try enhanced summaries (optional)
  continue-on-error: true
  run: python civicwatch/weekly_integration.py
```

**Pros:**
- Works everywhere (base summary always available)
- Enhanced summaries when possible
- No manual intervention needed

**Cons:**
- Enhanced summaries only when Ollama available
- In GitHub Actions, only base summary works

## Recommended Setup

### For Development/Local Use

1. **Install Ollama locally** (on your laptop)
2. **Run enhanced pipeline** when you want better summaries:
   ```bash
   python civicwatch/weekly_integration.py
   ```

3. **Commit summaries** to make them available on website:
   ```bash
   git add civicwatch/storage/summaries/reduce/
   git commit -m "Update AI-generated summaries"
   git push
   ```

### For Production/GitHub Actions

1. **Base workflow** (always runs):
   - Uses `weekly_overview.py` (no Ollama needed)
   - Generates simple, reliable summaries
   - Always works, even in cloud

2. **Optional enhancement** (if Ollama available):
   - Uses `weekly_integration.py`
   - Checks for Ollama availability
   - Falls back gracefully if not available

3. **Cached summaries** (committed to repo):
   - Pre-generated summaries in `civicwatch/storage/summaries/`
   - Loaded by website even when Ollama offline
   - Updated when you run locally and commit

## File Structure

```
civicwatch/
├── storage/
│   └── summaries/
│       ├── map/          # Chunk summaries (can commit)
│       └── reduce/        # Final summaries (can commit)
│
docs/
└── weekly/
    ├── latest.json        # Metadata (base + enhanced flags)
    ├── weekly_overview.txt           # Base summary
    └── weekly_overview_enhanced.txt  # Enhanced (if available)
```

## Website Integration

The website can check `latest.json`:

```javascript
const metadata = await fetch('weekly/latest.json');
const data = await metadata.json();

if (data.enhanced_available) {
    // Show enhanced summary
    displaySummary(data.enhanced_script);
} else {
    // Fall back to base summary
    displaySummary(data.script);
}
```

## Summary

**Best approach for your use case:**
1. Keep base `weekly_overview.py` (always works)
2. Run `weekly_integration.py` locally when laptop is on
3. Commit enhanced summaries to repo
4. Website uses cached summaries when Ollama unavailable

This gives you:
- ✅ Always-working base summaries
- ✅ Enhanced summaries when possible
- ✅ No cloud GPU costs
- ✅ Works even when laptop is off (cached summaries)

