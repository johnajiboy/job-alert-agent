"""
state_store.py
Component 4: Deduplication / State Store (Google Sheets version)

Uses a Google Sheet as the dedup log, per the assignment brief:
one row per job already posted -> columns: job_id, title, date_sent

Auth: a free Google Cloud service account (no billing required for Sheets
API at this volume). The service account's JSON key is stored as a GitHub
secret (GOOGLE_SERVICE_ACCOUNT_JSON) and loaded at runtime - never committed
to the repo.

Setup once:
  1. Enable the Google Sheets API in a free Google Cloud project.
  2. Create a Service Account, download its JSON key.
  3. Create a Google Sheet, share it with the service account's email
     (Editor access).
  4. Put the Sheet's ID (from its URL) in config.yaml as `google_sheet_id`.
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = ["job_id", "title", "date_sent"]


def _get_worksheet(config: dict):
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet_id = config["google_sheet_id"]
    sh = client.open_by_key(sheet_id)
    ws = sh.sheet1

    # Ensure header row exists
    values = ws.get_all_values()
    if not values:
        ws.append_row(HEADER)

    return ws


def load_state(config: dict) -> set:
    """Returns the set of job_ids already logged as sent."""
    try:
        ws = _get_worksheet(config)
        records = ws.get_all_records()  # skips header automatically
        return {str(r["job_id"]) for r in records if r.get("job_id")}
    except Exception as e:
        print(f"[state_store] failed to load state from Google Sheets: {e}")
        return set()


def save_new_sent(config: dict, jobs: list):
    """Appends newly-sent jobs as rows: job_id, title, date_sent."""
    if not jobs:
        return
    try:
        ws = _get_worksheet(config)
        now = datetime.now(timezone.utc).isoformat()
        rows = [[j["id"], j.get("title", ""), now] for j in jobs]
        ws.append_rows(rows)
        print(f"[state_store] appended {len(rows)} row(s) to Google Sheet")
    except Exception as e:
        print(f"[state_store] failed to save state to Google Sheets: {e}")
        raise


def filter_unseen(jobs: list, sent_ids: set) -> list:
    return [j for j in jobs if str(j["id"]) not in sent_ids]
