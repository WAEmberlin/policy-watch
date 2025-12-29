# GitHub Actions Setup & Troubleshooting

## Why Your Workflow Might Not Be Running Every 10 Minutes

The workflow is configured correctly (`*/10 * * * *`), but there are several things to check:

## 1. Enable GitHub Actions (Most Common Issue)

GitHub Actions must be enabled for your repository:

1. Go to your repository on GitHub
2. Click **Settings** (top menu)
3. Click **Actions** → **General** (left sidebar)
4. Under **Actions permissions**, ensure:
   - ✅ **Allow all actions and reusable workflows** is selected
   - OR **Allow local actions and reusable workflows** is selected
5. Scroll down to **Workflow permissions**
   - ✅ **Read and write permissions** should be selected
   - ✅ **Allow GitHub Actions to create and approve pull requests** (if you want auto-commits)
6. Click **Save**

## 2. Verify Workflow File Location

The workflow file must be in the **default branch** (usually `main` or `master`):

- ✅ File exists: `.github/workflows/daily.yml`
- ✅ File is in the default branch (not a feature branch)
- ✅ File has been committed and pushed

## 3. Check Workflow Status

1. Go to your repository on GitHub
2. Click the **Actions** tab (top menu)
3. You should see:
   - **"CivicWatch Update"** workflow listed
   - Recent runs showing success/failure
   - Scheduled runs appearing every 10 minutes

## 4. Scheduled Workflow Limitations

**Important Notes:**
- Scheduled workflows can have **delays** (GitHub doesn't guarantee exact timing)
- Workflows may be delayed during high load
- Minimum interval is **5 minutes** (your 10-minute schedule is fine)
- Workflows only run if the repository has been **active** (has had a push in the last 60 days)

## 5. Verify Workflow is Running

### Check Recent Runs:
1. Go to **Actions** tab
2. Click on **"CivicWatch Update"** workflow
3. You should see runs listed with timestamps
4. Click on a run to see:
   - ✅ Green checkmark = Success
   - ❌ Red X = Failed (check logs)
   - ⏸️ Yellow circle = In progress

### Check Logs:
- Click on a workflow run
- Expand each step to see logs
- Look for errors or warnings

## 6. Manual Test

Test the workflow manually to ensure it works:

1. Go to **Actions** tab
2. Click **"CivicWatch Update"** workflow
3. Click **"Run workflow"** button (top right)
4. Select branch (usually `main`)
5. Click **"Run workflow"**
6. Watch it execute in real-time

If manual runs work but scheduled runs don't, it's likely an Actions permissions issue.

## 7. Common Issues & Fixes

### Issue: "Workflow not showing in Actions tab"
**Fix**: 
- Ensure `.github/workflows/daily.yml` exists
- File is committed and pushed to default branch
- GitHub Actions is enabled (see #1 above)

### Issue: "Workflow runs but fails"
**Fix**:
- Check logs for error messages
- Verify all secrets are set (EMAIL_HOST, CONGRESS_API_KEY, etc.)
- Check Python dependencies are correct

### Issue: "Workflow runs but no commits"
**Fix**:
- Check if there are actual changes to commit
- Verify git permissions are set correctly
- Check workflow logs for "No changes" message

### Issue: "Scheduled runs not appearing"
**Fix**:
- Wait up to 10 minutes (scheduled workflows can be delayed)
- Check repository has been active (pushed to in last 60 days)
- Verify cron syntax is correct: `*/10 * * * *`
- Try manually triggering to ensure workflow works

## 8. Verify Cron Schedule

The cron expression `*/10 * * * *` means:
- `*/10` = Every 10 minutes
- `*` = Every hour
- `*` = Every day of month
- `*` = Every month
- `*` = Every day of week

**Expected behavior:**
- Runs at: :00, :10, :20, :30, :40, :50 of every hour
- 144 runs per day
- Runs 24/7

## 9. Check Repository Activity

GitHub may pause scheduled workflows if:
- Repository hasn't had a push in 60+ days
- Repository is archived
- Repository is private and you've exceeded free tier limits

**Fix**: Make a commit/push to reactivate workflows

## 10. GitHub Actions Limits

### Free Tier:
- **2,000 minutes/month** (shared across all workflows)
- Your workflow uses ~2-3 minutes per run
- 144 runs/day × 2.5 min = **360 minutes/day**
- **10,800 minutes/month** = ⚠️ **Exceeds free tier**

### If You Hit Limits:
- Workflows will stop running
- You'll see a message in Actions tab
- Options:
  1. Reduce frequency (every 30 min or hourly)
  2. Upgrade to GitHub Pro (3,000 min/month included)
  3. Purchase additional minutes

## Quick Checklist

- [ ] GitHub Actions enabled in repository settings
- [ ] Workflow file exists in `.github/workflows/daily.yml`
- [ ] File is in default branch (main/master)
- [ ] Workflow appears in Actions tab
- [ ] Can manually trigger workflow successfully
- [ ] Recent runs show success (green checkmarks)
- [ ] Repository has been active (push in last 60 days)
- [ ] Not exceeded GitHub Actions minute limits

## Still Not Working?

1. **Check Actions Tab**: Do you see the workflow listed?
2. **Check Recent Runs**: Are there any runs (successful or failed)?
3. **Try Manual Trigger**: Does it work when you click "Run workflow"?
4. **Check Settings**: Is Actions enabled in repository settings?
5. **Check Logs**: Are there any error messages?

If all else fails, the workflow might need to be re-enabled or there may be a repository permission issue.

