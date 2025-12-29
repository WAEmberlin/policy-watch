# Troubleshooting: Scheduled Workflows Not Running

## Common Issues & Solutions

### 1. Workflow File Location
**Problem**: Workflow must be in the **default branch** (usually `main` or `master`)

**Check**:
- Is `.github/workflows/daily.yml` in your default branch?
- If you're on a feature branch, merge to default branch

**Fix**:
```bash
# Check current branch
git branch

# If not on main/master, switch and merge
git checkout main
git merge your-feature-branch
git push
```

### 2. GitHub Actions Permissions
**Problem**: Actions might be disabled or have wrong permissions

**Check**:
1. Go to repository → **Settings** → **Actions** → **General**
2. Under "Actions permissions":
   - ✅ Must be enabled (not "Disable Actions")
   - ✅ "Allow all actions" or "Allow local actions"
3. Under "Workflow permissions":
   - ✅ "Read and write permissions" selected
   - ✅ "Allow GitHub Actions to create and approve pull requests" checked

**Fix**: Enable all required permissions and save

### 3. Repository Activity
**Problem**: GitHub pauses scheduled workflows if repo is inactive

**Check**: Has the repository had a push in the last 60 days?

**Fix**: Make a commit/push to reactivate:
```bash
git commit --allow-empty -m "Reactivate scheduled workflows"
git push
```

### 4. Cron Syntax Verification
**Problem**: Cron syntax might be incorrect

**Current**: `*/10 * * * *` (every 10 minutes)

**Verify**: 
- `*/10` = every 10 minutes
- `*` = every hour
- `*` = every day of month
- `*` = every month
- `*` = every day of week

**Test**: Use online cron validator to verify syntax

### 5. Scheduled Workflow Delays
**Problem**: GitHub doesn't guarantee exact timing

**Reality**: 
- Scheduled workflows can be delayed by minutes
- During high load, delays can be longer
- First scheduled run may take time to start

**Wait**: Give it 20-30 minutes after enabling

### 6. Workflow File Syntax Errors
**Problem**: YAML syntax errors prevent workflow from being recognized

**Check**:
1. Go to **Actions** tab
2. Look for "CivicWatch Update" workflow
3. If it doesn't appear, there's likely a syntax error

**Fix**: Validate YAML syntax:
- Use online YAML validator
- Check for indentation errors
- Ensure all quotes are properly closed

### 7. GitHub Free Tier Limits
**Problem**: May have hit usage limits

**Check**:
1. Go to repository → **Settings** → **Actions** → **Usage**
2. Check if you've exceeded free tier (2,000 minutes/month)

**Current Usage**: ~360 minutes/day = ~10,800 minutes/month
**Free Tier**: 2,000 minutes/month

**Status**: ⚠️ **Exceeds free tier** - workflows will stop when limit is hit

**Solutions**:
1. Reduce frequency (every 30 min or hourly)
2. Upgrade to GitHub Pro (3,000 min/month)
3. Purchase additional minutes

### 8. Workflow Not Visible in Actions Tab
**Problem**: Workflow file might not be recognized

**Check**:
- File path: `.github/workflows/daily.yml` (exact path)
- File extension: `.yml` or `.yaml` (both work)
- YAML syntax: Valid YAML format

**Fix**: 
1. Verify file exists: `ls .github/workflows/`
2. Check file content for syntax errors
3. Commit and push to default branch

### 9. Manual Runs Work But Scheduled Don't
**Problem**: Permissions or schedule configuration issue

**If manual runs work**:
- Workflow file is correct
- Permissions are likely OK
- Issue is with scheduled trigger

**Check**:
- Cron syntax in workflow file
- Default branch has the workflow file
- Repository is active (recent push)

### 10. Verify Scheduled Runs Are Enabled
**Problem**: Scheduled workflows might be disabled at account level

**Check** (if you have admin access):
1. GitHub account settings
2. Check if scheduled workflows are enabled
3. Some organizations disable scheduled workflows

## Step-by-Step Verification

1. **Check Workflow File**:
   ```bash
   cat .github/workflows/daily.yml
   ```
   Verify cron: `*/10 * * * *`

2. **Check Default Branch**:
   - Go to repository → Settings → General
   - Note the default branch name
   - Ensure workflow file is in that branch

3. **Check Actions Tab**:
   - Go to **Actions** tab
   - Look for "CivicWatch Update"
   - Check recent runs (should see manual runs)

4. **Check Permissions**:
   - Settings → Actions → General
   - Verify all permissions enabled

5. **Try Manual Run**:
   - Actions → CivicWatch Update → Run workflow
   - If manual works, scheduled should work too

6. **Wait and Monitor**:
   - Wait 20-30 minutes
   - Check Actions tab for scheduled runs
   - Look for runs at :00, :10, :20, :30, :40, :50

## Alternative: Reduce Frequency

If hitting limits, consider reducing frequency:

**Every 30 minutes** (48 runs/day):
```yaml
schedule:
  - cron: "*/30 * * * *"
```

**Every hour** (24 runs/day):
```yaml
schedule:
  - cron: "0 * * * *"
```

**Every 2 hours** (12 runs/day):
```yaml
schedule:
  - cron: "0 */2 * * *"
```

## Still Not Working?

1. **Check GitHub Status**: https://www.githubstatus.com/
2. **Review Workflow Logs**: Look for error messages
3. **Contact GitHub Support**: If all else fails
4. **Consider Alternative**: Use external cron service to trigger workflow via API

## Quick Test

Run this to verify workflow file is valid:
```bash
# Check if file exists and has correct cron
grep -A 2 "schedule:" .github/workflows/daily.yml
```

Expected output:
```yaml
  schedule:
    - cron: "*/10 * * * *"
```

