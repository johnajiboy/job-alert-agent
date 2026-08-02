"""
reasoner.py
Component 3: AI Reasoning Layer

Sends the raw, collected job list to Claude with the prompt structure
specified in the assignment brief: keep only jobs matching the keywords,
drop anything already in <already_sent>, and return a WhatsApp-ready
digest (or a fixed "no new jobs" string).

Note: local keyword/freshness filtering already happened in collector.py,
and local ID-based dedup already happened in state_store.py - Claude is
still given the full context (<already_sent> ids) and asked to re-check
both, as a second pass to catch near-duplicates across sources (e.g. the
same role posted on both RemoteOK and Remotive with different IDs) that
exact-ID matching alone would miss.
"""

import os
import json
from datetime import datetime, timezone
from anthropic import Anthropic

PROMPT_TEMPLATE = """<role>You are a job-alert formatting assistant for a WhatsApp group.</role>
<current_time_utc>{current_time_utc}</current_time_utc>
<instruction>
From the job listings provided in <jobs>, keep only roles matching
"{keywords}" posted within the last {max_age_hours} hours, computed
relative to <current_time_utc> above (each job's "posted_at" field is
already ISO-8601 or a similar parseable timestamp). Remove any job whose
"id" appears in <already_sent>. Also remove near-duplicate postings
(same role, same company, appearing under a different id from another
source) - keep only the first occurrence. Output a WhatsApp-ready digest
using the <output_format> below, keeping at most 2 jobs per message
(WhatsApp caps messages at 4096 characters and this fuller format takes
more space per job). If no new jobs qualify, output exactly:
"No new matching jobs this cycle."

CRITICAL - do not fabricate: only include the "Key Responsibilities",
"Requirements", contact email, and deadline sections/lines if that
information is genuinely present in the job's source "description" text.
If the description doesn't mention responsibilities, requirements, a
contact email, or a deadline, omit that section/line entirely rather than
inventing or guessing content. The overview sentence(s) must also be a
faithful summary of the actual description, not invented detail.

CRITICAL - output only the final digest: do not show your reasoning,
analysis, or any explanation of which jobs were included/excluded and
why. No preamble, no step-by-step walkthrough, no commentary before or
after the digest. Your entire response must be either the formatted
digest itself or the exact string "No new matching jobs this cycle." -
nothing else.
</instruction>
<jobs>{jobs_json}</jobs>
<already_sent>{sent_ids_json}</already_sent>
<output_format>
🚀 *[Title]*
🏢 Company: [Company]
📍 Location: [Location]
🏠 Work Mode: [Remote/Hybrid/Onsite, if stated - otherwise omit this line]

[2-4 sentence overview of the role, faithfully summarizing the source
description]

*Key Responsibilities:*
- [only if genuinely present in the source description]

*Requirements:*
- [only if genuinely present in the source description]

📧 Contact: [only if an email is genuinely present in the source description]
⏳ Deadline: [only if a deadline is genuinely present in the source description]
🔗 Apply: [link]

(repeat for each job, max 2 per message)
</output_format>
"""


def build_digest(jobs: list, sent_ids: set, config: dict) -> str | None:
    """Calls Claude with the brief's prompt format. Returns the WhatsApp
    message text, or None if there's nothing new to send."""
    if not jobs:
        return None

    prompt = PROMPT_TEMPLATE.format(
        current_time_utc=datetime.now(timezone.utc).isoformat(),
        keywords=", ".join(config.get("keywords", [])),
        max_age_hours=config.get("max_age_hours", 2),
        jobs_json=json.dumps(jobs[:30], indent=2),
        sent_ids_json=json.dumps(list(sent_ids)),
    )

    try:
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=config.get("llm_model_anthropic", "claude-sonnet-4-6"),
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:
        print(f"[reasoner] Claude call failed: {e}")
        text = _fallback_format(jobs, sent_ids)

    if text.strip() == "No new matching jobs this cycle.":
        return None

    return text


def _fallback_format(jobs: list, sent_ids: set) -> str:
    """Deterministic formatter used only if the Claude API call itself
    errors out, so a transient API issue doesn't lose a run entirely.
    Roughly mirrors the richer PROMPT_TEMPLATE style, but with no LLM to
    judge what's genuinely present - it just prints whatever fields exist
    on the job dict and skips whatever's empty, capped at 2 jobs per
    message for the same 4096-character WhatsApp limit reason."""
    unseen = [j for j in jobs if str(j["id"]) not in sent_ids][:2]
    if not unseen:
        return "No new matching jobs this cycle."

    blocks = []
    for j in unseen:
        lines = [f"🚀 *{j.get('title', '')}*"]
        if j.get("company"):
            lines.append(f"🏢 Company: {j['company']}")
        if j.get("location"):
            lines.append(f"📍 Location: {j['location']}")
        if j.get("description"):
            lines.append("")
            lines.append(j["description"])
        if j.get("url"):
            lines.append("")
            lines.append(f"🔗 Apply: {j['url']}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
