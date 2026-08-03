# Autonomous Job-Alert AI Agent for WhatsApp

**Chosen function:** Guide function — search job boards for postings
matching keywords (e.g. "AI Engineer", "Remote Developer") and post a
formatted digest to WhatsApp every 2 hours, fully autonomously, using only
free tools.

**Free-tool stack used:**
- Scheduler → GitHub Actions (free cron)
- Data Collector → RemoteOK API, Remotive API, Arbeitnow API, WeWorkRemotely RSS
- AI Reasoning Layer → Claude (Anthropic API)
- Dedup/State Store → Google Sheets (free, via a service account)
- Delivery Layer → WhatsApp Cloud API (Meta's free tier / test number)

---

## Step 1 — Set up accounts (all free)

1. **Anthropic Console** (console.anthropic.com) → sign up → API Keys →
   create a key. This gives you `ANTHROPIC_API_KEY`.
2. **Meta Developer account** (developers.facebook.com) → Create App →
   type "Business" → add the **WhatsApp** product. Meta auto-provisions a
   **free test phone number**. From WhatsApp → API Setup, copy:
   - the **temporary access token** → `WHATSAPP_TOKEN`
   - the **Phone Number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   Add your own number under "To" as a test recipient and verify it with
   the code Meta texts you — that's how a number/group gets opted in
   during testing.
   *(For unattended production use, the temporary token expires in 24h —
   generate a permanent one via a System User in Business Settings.)*
3. **GitHub account** → create a new repo, push this project to it.
4. **Google account** → console.cloud.google.com → enable the **Google
   Sheets API** → **IAM & Admin → Service Accounts → Create** → generate a
   **JSON key** (this whole JSON file's contents become the
   `GOOGLE_SERVICE_ACCOUNT_JSON` secret). Then create a blank Google Sheet
   (e.g. named `job-alert-state`) and **share it** with the service
   account's email — found inside the JSON, looks like
   `xxx@xxx.iam.gserviceaccount.com` — with **Editor** access. Copy the
   Sheet's ID from its URL into `config.yaml` as `google_sheet_id`.

---

## Step 2 — Data Collector (`collector.py`)

Pulls from free, keyless job APIs/RSS: RemoteOK, Remotive, Arbeitnow,
WeWorkRemotely RSS. These substitute for LinkedIn/Facebook/X, which have no
free public API for job posts and forbid scraping in their ToS — using
official public feeds instead keeps this compliant, per the brief's
Compliance & Safety Notes. Filters by keyword match and by `max_age_hours`
(default 2, matching the brief).

## Step 3 — AI Reasoning Layer (`reasoner.py`)

Sends jobs to Claude using the exact prompt structure from the brief
(`<role>`, `<instruction>`, `<jobs>`, `<already_sent>`, `<output_format>`
tags), asking it to keep only matching/fresh/unseen jobs and return either
a WhatsApp-ready digest or the literal string `"No new matching jobs this
cycle."` — this is the prompt you'll paste into your submission.

## Step 4 — Deduplication / State Store (`state_store.py`)

Uses the Google Sheet as the log: one row per sent job —
`job_id | title | date_sent`. Before sending, `load_state()` reads all
existing job_ids; after a successful send, `save_new_sent()` appends the
new rows.

## Step 5 — Delivery Layer (`delivery.py`)

Posts the digest via the WhatsApp Cloud API's free `Send Message` endpoint
to each number in `config.yaml → whatsapp_cloud_api.recipients`.

> **Group note:** the Cloud API sends to individual numbers/threads, not a
> group-chat ID — there's no free "post into a group" endpoint on Meta's
> official API. To satisfy "post into a WhatsApp group" while staying
> ToS-compliant and free, either (a) list every opted-in group member's
> number in `recipients` so each gets the digest, or (b) create a WhatsApp
> **broadcast list** of the same contacts, which reads like a group to
> recipients. Document whichever you choose in your write-up.

## Step 6 — Schedule it every 2 hours (`.github/workflows/job-agent.yml`)

GitHub Actions, `cron: "0 */2 * * *"`, plus `workflow_dispatch` for manual
test runs from the Actions tab. Add these 4 repo secrets under
**Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from Step 1.1 |
| `WHATSAPP_TOKEN` | from Step 1.2 |
| `WHATSAPP_PHONE_NUMBER_ID` | from Step 1.2 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | full contents of the JSON key from Step 1.4 |

Also fill in `config.yaml`: your `google_sheet_id` and the `recipients`
phone numbers.

## Step 7 — Test, then let it run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
export WHATSAPP_TOKEN=...
export WHATSAPP_PHONE_NUMBER_ID=...
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
python main.py
```

Then in GitHub: **Actions tab → job-agent → Run workflow** to trigger it
manually and confirm a real WhatsApp message arrives. Let it run
unattended for at least 3 full cycles (6 hours) and confirm no duplicate
jobs are posted — check the Google Sheet log to verify. For your
submission, screenshot: the Actions run history (3+ green runs, 2h apart),
the WhatsApp messages received, and the Google Sheet rows.

---

## Compliance & Safety Notes

- Only official public RSS/JSON endpoints are used for job data — no
  scraping of logged-in or private pages.
- Each source's rate limits are respected (one fetch per source per
  2-hour cycle).
- Only numbers that have explicitly opted in (verified as test recipients,
  or members of a broadcast list you administer) receive messages.



```
GitHub Actions cron (every 2h)
        │
        ▼
  collector.py  ──fetches──▶ RemoteOK / Remotive / Arbeitnow / WWR RSS
        │  (keyword + freshness filter)
        ▼
  state_store.py ──reads Google Sheet, drops already-sent job_ids
        │
        ▼
  reasoner.py  ──calls──▶ Claude (Anthropic API)
        │  (re-check freshness/dedup, format WhatsApp digest)
        ▼
  delivery.py  ──calls──▶ WhatsApp Cloud API ──▶ recipients/group
        │
        ▼
  state_store.py ──appends new job_id rows to the Google Sheet
```
