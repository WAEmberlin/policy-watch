# Email Digest Setup

PolicyWatch can send **separate email digests** for each tracked state plus federal and a combined all-states digest.

**Recipient email addresses are never stored in the repository.** They live only in GitHub Secrets and are delivered via **BCC** so recipients cannot see each other.

`policywatchadmin@gmail.com` is always BCC'd on every digest. Other addresses come from `EMAIL_DIGEST_RECIPIENTS`. A digest with no extra recipients still goes to that operator address when it has items; empty windows are skipped (`Skipping digest 'xx' — no items in window`).

When a digest includes veteran-related bills, a **Veteran Legislation** section appears at the top. Those bills are not repeated in the Updates lists below. Veteran bill numbers are highlighted red / yellow / green to match the cards on the site.

---

## Digest types

| Digest ID | Subject example | Contents |
|-----------|-----------------|----------|
| `ks` | Kansas PolicyWatch — … | Kansas updates first, then federal |
| `co` | Colorado PolicyWatch — … | Colorado first, then federal |
| `az` | Arizona PolicyWatch — … | Arizona first, then federal |
| `ut` | Utah PolicyWatch — … | Utah first, then federal |
| `me` | Maine PolicyWatch — … | Maine first, then federal |
| `ne` | Nebraska PolicyWatch — … | Nebraska first, then federal |
| `md` | Maryland PolicyWatch — … | Maryland first, then federal |
| `pa` | Pennsylvania PolicyWatch — … | Pennsylvania first, then federal |
| `ma` | Massachusetts PolicyWatch — … | Massachusetts first, then federal |
| `wv` | West Virginia PolicyWatch — … | West Virginia first, then federal |
| `tn` | Tennessee PolicyWatch — … | Tennessee first, then federal |
| `nc` | North Carolina PolicyWatch — … | North Carolina first, then federal |
| `mo` | Missouri PolicyWatch — … | Missouri first, then federal |
| `ia` | Iowa PolicyWatch — … | Iowa first, then federal |
| `ga` | Georgia PolicyWatch — … | Georgia first, then federal |
| `ky` | Kentucky PolicyWatch — … | Kentucky first, then federal |
| `federal` | Federal PolicyWatch — … | U.S. Congress only |
| `all` | PolicyWatch — All States — … | All states (alphabetical), then federal at bottom |
| `federal_vets` | Federal Veteran PolicyWatch — … | U.S. Congress **veteran bills only** |
| `all_vets` | Veteran PolicyWatch — … | Veteran bills from all states plus Congress |
| `ks_vets`, `ma_vets`, … | Kansas Veteran PolicyWatch — … | That state's **veteran bills only** |

Each digest includes:
- Bill/legislation updates from the **last 24 hours**
- Hearings scheduled **today and tomorrow** for that jurisdiction
- **Veteran Legislation** at the top when any veteran bills are in that window (hearings stay in the hearing sections)
- Veteran-only digests (`federal_vets`, `all_vets`, `ks_vets`, …) list veteran bills only (no hearings, no non-veteran updates). Assign extra people in the same `EMAIL_DIGEST_RECIPIENTS` JSON as the regular digests. `policywatchadmin@gmail.com` is already on every list.

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
  "me": ["maine-person@example.com"],
  "ne": ["nebraska-person@example.com"],
  "md": ["maryland-person@example.com"],
  "pa": ["pennsylvania-person@example.com"],
  "ma": ["massachusetts-person@example.com"],
  "wv": ["west-virginia-person@example.com"],
  "tn": ["tennessee-person@example.com"],
  "nc": ["north-carolina-person@example.com"],
  "mo": ["missouri-person@example.com"],
  "ia": ["iowa-person@example.com"],
  "ga": ["georgia-person@example.com"],
  "ky": ["kentucky-person@example.com"],
  "federal": ["congress-watcher@example.com"],
  "all": ["you@example.com", "team-lead@example.com"],
  "federal_vets": ["veteran-congress@example.com"],
  "all_vets": ["veteran-all-states@example.com"],
  "ks_vets": ["kansas-veterans@example.com"]
}
```

Rules:
- Keys must match digest IDs: regular (`ks`, `federal`, `all`, …) or veteran-only (`federal_vets`, `all_vets`, `ks_vets`, `ma_vets`, …)
- Values are arrays of email addresses (or a comma-separated string)
- **Omit a key or use `[]`** if only the operator copy should go out for that digest
- Same person can appear on multiple lists

### Alternative: separate secrets per digest

Instead of one JSON blob, you can set `EMAIL_RECIPIENTS_<DIGEST>` (comma-separated addresses). These override the JSON for that digest:

- `EMAIL_RECIPIENTS_KS`
- `EMAIL_RECIPIENTS_CO`
- `EMAIL_RECIPIENTS_AZ`
- `EMAIL_RECIPIENTS_UT`
- `EMAIL_RECIPIENTS_ME`
- `EMAIL_RECIPIENTS_NE`
- `EMAIL_RECIPIENTS_MD`
- `EMAIL_RECIPIENTS_PA`
- `EMAIL_RECIPIENTS_MA`
- `EMAIL_RECIPIENTS_WV`
- `EMAIL_RECIPIENTS_TN`
- `EMAIL_RECIPIENTS_NC`
- `EMAIL_RECIPIENTS_MO`
- `EMAIL_RECIPIENTS_IA`
- `EMAIL_RECIPIENTS_GA`
- `EMAIL_RECIPIENTS_KY`
- `EMAIL_RECIPIENTS_FEDERAL`
- `EMAIL_RECIPIENTS_ALL`
- `EMAIL_RECIPIENTS_FEDERAL_VETS`
- `EMAIL_RECIPIENTS_ALL_VETS`

### Legacy fallback

If only `EMAIL_TO` is set (old setup), it receives the **`all`** digest only.

---

## Privacy

- Other recipients are **not** in config files; they live in GitHub Secrets. The operator copy (`policywatchadmin@gmail.com`) is always added in code.
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

Emails run **once daily** at 11:00 UTC (6:00 AM Central during CDT) via `.github/workflows/daily_email.yml`. That job restores `data/normalized/bills.json` from R2 before sending so Open States state updates (Massachusetts, Missouri, Iowa, and the other tracked states) are included. Federal bills and Utah committee hearings still come from the committed `src/output/` files. If the R2 restore fails, digests still send from the checkout, and an ops alert goes to `policywatchadmin@gmail.com` (`EMAIL_OPS_ALERT`).

---

## Adding a new state later

1. Add the state to `config/states.yaml`
2. Add a digest entry to `config/email_digests.yaml`
3. Add `EMAIL_RECIPIENTS_XX` to `.github/workflows/daily_email.yml` if you use per-digest secrets
4. Add a recipient key to the `EMAIL_DIGEST_RECIPIENTS` JSON secret (or the per-digest secret)
