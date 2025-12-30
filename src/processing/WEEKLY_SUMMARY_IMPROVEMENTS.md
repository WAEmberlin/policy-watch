# Weekly Summary Improvements

## Problem

The original weekly summary was too minimal:
- Only showed ONE sample item per category
- Truncated titles at 80 characters with "..."
- No actual content/summaries from items
- Very brief and uninformative

## Solution: Enhanced Summarization (No GPU Required)

I've created an improved summary system that:

### 1. **Shows More Items**
- Up to 5 items per category (instead of just 1)
- Better item selection based on relevance and content quality

### 2. **Includes Actual Content**
- Extracts summaries from items when available
- Uses intelligent sentence extraction for items with text
- Shows bill numbers, hearing dates, committees

### 3. **Better Formatting**
- Clear section headers (=== CONGRESSIONAL ACTIVITY ===)
- Numbered lists for easy reading
- Smart truncation at word boundaries (not mid-word)
- Preserves important information

### 4. **Extractive Summarization**
- Uses simple but effective text analysis
- Scores sentences by keyword density, position, length
- Extracts key information without needing LLMs

### 5. **Graceful Fallback**
- Enhanced module tries to use better algorithms
- Falls back to improved simple version if enhanced module unavailable
- Always produces readable output

## Files

- **`weekly_summary_enhanced.py`**: New enhanced summary generator
- **`weekly_overview.py`**: Updated to use enhanced version with fallback

## Optional Dependency

For even better summarization, you can install `sumy`:

```bash
pip install sumy
```

This provides TextRank and LSA summarization algorithms. The system works fine without it, but `sumy` provides better sentence extraction.

## Example Output

**Before (old):**
```
In Congress, 12 bills, including H.R. 1234: Improving Civic Transp... were tracked this week.
```

**After (new):**
```
=== CONGRESSIONAL ACTIVITY ===

**Bills (12 total):**

1. H.R. 1234: Improving Civic Transparency Act
   This bill requires government agencies to publish meeting minutes within 48 hours and extends public comment periods to 30 days for major policy changes.
   (HR 1234)

2. S. 5678: Education Funding Reform
   Proposes restructuring federal education funding to prioritize underserved communities and increase transparency in allocation.
   (S 5678)

... and 10 more bills.
```

## Benefits

✅ **More informative**: Shows actual content, not just titles
✅ **Better structure**: Clear sections, numbered lists
✅ **No GPU needed**: Works in GitHub Actions
✅ **No external APIs**: Pure Python, no costs
✅ **Backward compatible**: Falls back gracefully if enhanced module unavailable

## Usage

The enhanced summary is automatically used by `weekly_overview.py`. No changes needed to your workflow - it just works better!

To test locally:
```bash
python -m src.processing.weekly_overview
```

