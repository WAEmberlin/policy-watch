# Verify Scheduled Workflows Are Running

Since your workflow file is in `main` and manual runs work, here's how to verify scheduled runs:

## What to Check

### 1. Wait for Next Hour
After committing the hourly schedule change:
- Wait until the next :00 (e.g., if it's 3:15 PM, wait until 4:00 PM)
- Check Actions tab for a scheduled run
- Scheduled runs show a clock icon (🕐) instead of a play button

### 2. Check for Scheduled Run Indicators
In the Actions tab, scheduled runs will show:
- **Clock icon** (🕐) - indicates it was triggered by schedule
- **"scheduled"** in the run name/description
- Timestamp at :00 of the hour

### 3. Verify Workflow File Was Recently Updated
GitHub may need a recent commit to "activate" scheduled workflows:
- Make sure the workflow file change is committed and pushed
- If you just updated it, GitHub may need a few minutes to recognize it

### 4. Check Repository Activity
GitHub pauses scheduled workflows if:
- Repository hasn't had a push in 60+ days
- Repository appears inactive

**Fix**: Make a new commit to reactivate:
```bash
git commit --allow-empty -m "Reactivate scheduled workflows"
git push
```

### 5. Verify Cron Syntax
The current cron is: `0 * * * *`
- This means: at minute 0 of every hour
- Should run: 12:00 AM, 1:00 AM, 2:00 AM, ... 11:00 PM

## If Still Not Working

If scheduled runs still don't appear after the next hour:

1. **Check GitHub Status**: https://www.githubstatus.com/
   - Scheduled workflows might be experiencing issues

2. **Verify Workflow File Syntax**:
   - Open `.github/workflows/daily.yml` on GitHub
   - Check if there are any syntax errors (red indicators)

3. **Check Organization/Account Settings**:
   - If this is an organization repo, check org settings
   - Some organizations disable scheduled workflows

4. **Try a Different Schedule** (temporary test):
   - Change to `*/15 * * * *` (every 15 minutes) to test
   - See if shorter interval triggers faster
   - Then change back to hourly

## Expected Behavior

After committing the hourly schedule:
- **First scheduled run**: Should appear at the next :00
- **Subsequent runs**: Every hour at :00
- **24 runs per day**: One per hour

## Quick Test

To verify the schedule is recognized:
1. Go to Actions tab
2. Click "CivicWatch Update" workflow
3. Look at the workflow details - it should show the schedule
4. Wait for the next hour and check for a scheduled run

If manual runs work but scheduled don't appear, it's likely a GitHub-side delay or the repository needs to be "reactivated" with a new commit.


