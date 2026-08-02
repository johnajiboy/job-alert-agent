"""
main.py
Orchestrator - wires the 5 required components together.
Invoked by GitHub Actions on a cron schedule (see .github/workflows/job-agent.yml).

Flow:
  Scheduler (GH Actions) -> Collector -> State Store (Google Sheets, filter seen)
  -> Reasoning Layer (Claude) -> Delivery (WhatsApp Cloud API) ->
  State Store (append newly-sent rows)
"""

import sys
import time
import yaml

from collector import collect_jobs
from state_store import load_state, save_new_sent, filter_unseen
from reasoner import build_digest
from delivery import send_whatsapp_message


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run():
    config = load_config()

    # 1. Trigger/Scheduler: this script being invoked at all IS the trigger,
    #    controlled entirely by the cron schedule in the GH Actions workflow.

    # 2. Data Collector
    raw_jobs = collect_jobs(config)
    if not raw_jobs:
        print("[main] no jobs matched keywords this run - exiting cleanly")
        return

    # 4a. Deduplication - drop anything already logged in the Google Sheet
    sent_ids = load_state(config)
    new_jobs = filter_unseen(raw_jobs, sent_ids)
    if not new_jobs:
        print("[main] all matched jobs were already sent previously - nothing new")
        return

    print(f"[main] {len(new_jobs)} new job(s) to process")

    # 3. AI Reasoning Layer - filter noise + format for WhatsApp, one
    #    message per job rather than a single bundled digest
    messages = build_digest(new_jobs, sent_ids, config)
    if not messages:
        print("[main] Claude determined nothing worth sending - exiting cleanly")
        return

    # 5. Delivery Layer - send each job as its own separate message, with
    #    a short delay so they arrive as distinct WhatsApp messages
    #    instead of all landing at once.
    all_sent_ok = True
    for i, message in enumerate(messages):
        if not send_whatsapp_message(message, config):
            all_sent_ok = False
        if i < len(messages) - 1:
            time.sleep(2)

    # 4b. Only log jobs as "sent" if every message in the batch actually
    #     delivered, so a partial failure doesn't silently lose a job.
    if all_sent_ok:
        save_new_sent(config, new_jobs)
    else:
        print("[main] delivery failed - NOT updating state, will retry next run")
        sys.exit(1)  # non-zero exit so the GH Actions run is visibly marked failed


if __name__ == "__main__":
    run()
