# Email Digest Setup

PolicyWatch can send **separate email digests** for each state plus federal and a combined all-states digest.

**Recipient email addresses are never stored in the repository.** They live only in GitHub Secrets and are delivered via **BCC** so recipients cannot see each other.

---

## Digest types

| Digest ID | Subject example | Contents |
|-----------|-----------------|----------|
| `ks` | Kansas PolicyWatch — … | Kansas updates first, then federal |
| `co` | Colorado PolicyWatch — … | Colorado first, then federal |
| `az` | Arizona PolicyWatch — … | Arizona first, then federal |
| `ut` | Utah PolicyWatch — … | Utah first, then federal |
| `federal` | Federal PolicyWatch — … | U.S. Congress only |
| `all` | PolicyWatch — All States — … | AZ, CO, KS, UT (alphabetical), then federal at bottom |

Each digest includes:
- Bill/legislation updates from the **last 6 hours**
- **Tomorrow's hearings** for that jurisdiction

---

## Step 1: SMTP secrets (if not already set)

In GitHub → **Settings → Secrets and variables → Actions**, set:

| Secret | Description |
|--------|-------------|
| `EMAIL_HOST` | SMTP server (e.g. `smtp.gmail.com`) |
| `EMAIL_PORT` | Usually `587` |
| `EMAIL_USER` | SMTP login |
| `EMAIL_PASS` | SMTP password or app password |
| `EMAIL_FROM` | Optional — visible From address (defaults to `EMAIL_USER`) |

---

## Step 2: Assign recipients (one JSON secret)

Create secret: **`EMAIL_DIGEST_RECIPIENTS`**

Paste JSON like this (use real addresses — this is an example only):

```json
{
  "ks": ["kansas-person@example.com"],
  "co": ["colorado-person@example.com"],
  "az": ["arizona-person@example.com"],
  "ut": ["utah-person@example.com"],
  "federal": ["congress-watcher@example.com"],
  "all": ["you@example.com", "team-lead@example.com"]
}
```

Rules:
- Keys must be: `ks`, `co`, `az`, `ut`, `federal`, `all`
- Values are arrays of email addresses (or a comma-separated string)
- **Omit a key or use `[]`** to skip that digest entirely
- Same person can appear on multiple lists

### Alternative: separate secrets per digest

Instead of one JSON blob, you can set:

- `EMAIL_RECIPIENTS_KS`
- `EMAIL_RECIPIENTS_CO`
- `EMAIL_RECIPIENTS_AZ`
- `EMAIL_RECIPIENTS_UT`
- `EMAIL_RECIPIENTS_FEDERAL`
- `EMAIL_RECIPIENTS_ALL`

Each value is comma-separated addresses. These override the JSON for that digest.

### Legacy fallback

If only `EMAIL_TO` is set (old setup), it receives the **`all`** digest only.

---

## Privacy

- Addresses are **not** in code or config files committed to GitHub
- Emails are sent with **BCC** — each recipient only sees the From address
- GitHub Actions logs show **recipient counts**, not addresses
- Only GitHub repo admins can view secret values

---

## Step 3: Test

Manual run from GitHub → **Actions → Email Updates → Run workflow**

Or locally (do not commit `.env`):

```powershell
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_USER = "you@example.com"
$env:EMAIL_PASS = "your-app-password"
$env:EMAIL_DIGEST_RECIPIENTS = '{"ks":["you@example.com"],"all":["you@example.com"]}'
python src/processing/send_email.py --dry-run
python src/processing/send_email.py --digest ks
```

---

## Schedule

Emails run every **6 hours** via `.github/workflows/daily_email.yml`.

---

## Adding a new state later

1. Add state to `config/states.yaml`
2. Add digest entry to `config/email_digests.yaml`
3. Add recipient key to `EMAIL_DIGEST_RECIPIENTS` JSON
