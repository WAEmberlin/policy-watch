# Check Workflow Status - Step by Step

## Immediate Checks

### 1. Verify Workflow File is in Default Branch

**Critical**: The workflow file MUST be in your default branch (usually `main` or `master`).

**Check**:
- Go to your repository on GitHub
- Look at the branch dropdown (top left)
- What branch are you currently viewing?
- Is `.github/workflows/daily.yml` visible in that branch?

**If on a feature branch**:
- The workflow won't run until it's merged to the default branch
- Merge your changes to `main`/`master`

### 2. Check Actions Tab

1. Go to **Actions** tab in your repository
2. Do you see **"CivicWatch Update"** in the workflow list?
   - ✅ **Yes**: Workflow is recognized, continue to step 3
   - ❌ **No**: Workflow file might not be in default branch or has syntax errors

### 3. Check Recent Runs

In the Actions tab, look at recent runs:
- Do you see any runs at all?
- Are they all manual (triggered by you)?
- Do you see any scheduled runs (would show a clock icon)?

### 4. Check Repository Settings

1. Go to **Settings** → **Actions** → **General**
2. Under **"Actions permissions"**:
   - Must NOT be "Disable Actions"
   - Should be "Allow all actions" or "Allow local actions"
3. Under **"Workflow permissions"**:
   - Must be "Read and write permissions"
   - Check "Allow GitHub Actions to create and approve pull requests"
4. Click **Save** if you made changes

### 5. Check Usage Limits

1. Go to **Settings** → **Actions** → **Usage**
2. Check if you've exceeded the free tier (2,000 minutes/month)
3. If exceeded, workflows will stop running

**Your usage**: ~360 minutes/day = ~10,800 minutes/month
**Free tier**: 2,000 minutes/month
**Status**: ⚠️ **You're exceeding the free tier**

## Most Likely Issues

### Issue #1: Exceeded Free Tier Limits
**Symptom**: Workflows stop running mid-month
**Solution**: 
- Reduce frequency to every 30 minutes or hourly
- Upgrade to GitHub Pro
- Purchase additional minutes

### Issue #2: Workflow Not in Default Branch
**Symptom**: Only manual runs work, no scheduled runs
**Solution**: Merge workflow file to default branch

### Issue #3: Repository Inactive
**Symptom**: No runs at all
**Solution**: Make a commit/push to reactivate

## Quick Fix: Reduce Frequency

Since you're exceeding free tier limits, consider reducing frequency:

**Every 30 minutes** (48 runs/day, ~2,880 min/month):
```yaml
schedule:
  - cron: "*/30 * * * *"
```

**Every hour** (24 runs/day, ~1,440 min/month):
```yaml
schedule:
  - cron: "0 * * * *"
```

This will stay within free tier limits and still update frequently.

## Test Right Now

1. **Manual run**: Trigger workflow manually - does it work?
2. **Check branch**: Is workflow file in default branch?
3. **Check settings**: Are Actions permissions enabled?
4. **Check usage**: Have you exceeded free tier?

Let me know what you find and I can help fix the specific issue!

