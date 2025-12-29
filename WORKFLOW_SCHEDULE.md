# Workflow Schedule Configuration

## Current Schedule

The CivicWatch workflow runs **every 10 minutes** to keep the website updated with the latest data.

## Schedule Details

- **Cron Expression**: `*/10 * * * *` (every 10 minutes)
- **Runs**: 144 times per day (every 10 minutes, 24/7)
- **Email**: Only sent once per day at 6:30 PM Central (00:30 UTC)

## What Happens Each Run

1. **Fetch RSS Feeds** (US Congress, VA News)
2. **Fetch Kansas Legislature RSS Feeds** (House, Senate, Committee, Bills)
3. **Fetch Congress.gov API Bills** (if API key is configured)
4. **Generate Site Data** (combines all sources into `site_data.json`)
5. **Send Email** (only at 6:30 PM Central / 00:30 UTC)
6. **Commit & Push Updates** (if there are changes)

## Email Schedule

Emails are sent only once per day to avoid spam:
- **Time**: 6:30 PM Central Time (00:30 UTC)
- **Logic**: Checks if current hour is 00 and minute is 30
- **Other Runs**: Email step is skipped with a log message

## GitHub Actions Limits

### Free Tier Limits
- **Workflow Runs**: 2,000 minutes per month (shared across all workflows)
- **Concurrent Jobs**: 20 jobs maximum
- **Scheduled Workflows**: Minimum 5-minute interval

### Our Usage
- **Runs per day**: 24 (every hour)
- **Minutes per run**: ~2-3 minutes
- **Monthly usage**: ~1,440-2,160 minutes
- **Status**: ✅ **Within free tier limit** (2,000 minutes/month)

### Recommendations

If you hit GitHub Actions limits, consider:

1. **Reduce Frequency**:
   - Change to every 30 minutes: `*/30 * * * *` (48 runs/day)
   - Change to every hour: `0 * * * *` (24 runs/day)
   - Change to every 2 hours: `0 */2 * * *` (12 runs/day)

2. **Upgrade to GitHub Pro**:
   - 3,000 minutes/month included
   - Additional minutes available for purchase

3. **Optimize Workflow**:
   - Only commit if there are actual changes (already implemented)
   - Skip API calls if no new data expected

## Changing the Schedule

To modify the update frequency, edit `.github/workflows/daily.yml`:

```yaml
on:
  schedule:
    - cron: "*/10 * * * *"  # Change this line
```

### Common Cron Patterns

- Every 5 minutes: `*/5 * * * *`
- Every hour: `0 * * * *` (current)
- Every 15 minutes: `*/15 * * * *`
- Every 30 minutes: `*/30 * * * *`
- Every hour: `0 * * * *`
- Every 2 hours: `0 */2 * * *`
- Every 6 hours: `0 */6 * * *`
- Once daily: `30 0 * * *` (00:30 UTC = 6:30 PM Central)

## Manual Triggers

You can manually trigger the workflow:
1. Go to GitHub Actions tab
2. Select "CivicWatch Update" workflow
3. Click "Run workflow" button

## Monitoring

Check workflow status:
- **GitHub Actions Tab**: View run history and logs
- **Workflow Runs**: See success/failure status
- **Logs**: Check each step for errors

## Troubleshooting

### Workflow Not Running
- Check GitHub Actions is enabled for the repository
- Verify cron syntax is correct
- Check repository settings → Actions → General

### Too Many Runs
- Reduce frequency in cron schedule
- Consider upgrading GitHub plan
- Optimize workflow steps

### Email Not Sending
- Verify email is only sent at 00:30 UTC
- Check email credentials in repository secrets
- Review email step logs

