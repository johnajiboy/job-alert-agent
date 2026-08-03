# AI Reasoning Layer — Prompt Documentation

This is the exact prompt template sent to Claude (Anthropic API) each cycle,
implemented in `reasoner.py` as `PROMPT_TEMPLATE`. The `{current_time_utc}`,
`{keywords}`, `{max_age_hours}`, `{jobs_json}`, and `{sent_ids_json}`
placeholders are filled in at runtime before the request is sent.

```
<role>You are a job-alert formatting assistant for a WhatsApp group.</role>
<current_time_utc>{current_time_utc}</current_time_utc>
<instruction>
From the job listings provided in <jobs>, keep only roles matching
"{keywords}" posted within the last {max_age_hours} hours, computed
relative to <current_time_utc> above (each job's "posted_at" field is
already ISO-8601 or a similar parseable timestamp). Remove any job whose
"id" appears in <already_sent>. Also remove near-duplicate postings
(same role, same company, appearing under a different id from another
source) - keep only the first occurrence. Keep at most 5 qualifying jobs
total.

Each qualifying job is sent to WhatsApp as its own separate message, not
bundled together. Output each job as a complete, standalone message using
the <output_format> below. If more than one job qualifies, separate
consecutive job messages with a line containing exactly
"===JOB_BREAK===" and nothing else on that line - no delimiter before the
first job or after the last one. If no new jobs qualify, output exactly:
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
</output_format>
```

## Design notes

- **Why XML tags:** delimiting `<jobs>` and `<already_sent>` clearly stops
  the model from confusing "already sent" ids with new job data, and makes
  the instruction unambiguous about which block to filter against.
- **Why a hard "no new jobs" sentinel string:** `reasoner.py`'s
  `build_digest()` checks for this exact string to decide whether to return
  an empty list rather than sending a WhatsApp message that cycle. Without a
  fixed sentinel, a slightly reworded "nothing to report" reply from the
  model could accidentally get sent to the group as a real message.
- **Why `===JOB_BREAK===` instead of one bundled digest:** each job is
  delivered as its own separate WhatsApp message rather than all jobs
  packed into one message/thread. `build_digest()` splits Claude's raw
  response on this exact delimiter into a list of message strings, and
  `main.py` sends each one individually (with a short delay between sends
  so they arrive as distinct messages). The delimiter must appear on its
  own line, only *between* jobs - never before the first or after the last.
- **Why `<current_time_utc>`:** the model has no other way to judge "posted
  within the last N hours" - without an explicit current-time reference it
  can only guess, especially since the model's training cutoff predates the
  actual run date. Passing it explicitly lets the freshness re-check be a
  real calculation instead of a guess.
- **Why the no-fabrication instruction:** the richer per-job format has
  sections (Key Responsibilities, Requirements, contact email, deadline)
  that don't exist in every source posting. Without an explicit
  instruction, an LLM asked to "fill in" a structured template tends to
  invent plausible-sounding content for missing fields - this forces it to
  omit a section entirely rather than fabricate.
- **Why the no-reasoning instruction:** without it, the model may preface
  the digest with its own analysis of which jobs it kept/dropped and why.
  Since `main.py` sends the model's output more or less directly to
  WhatsApp, any such preamble would otherwise be delivered as part of the
  message.
- **Belt-and-suspenders dedup:** `already_sent` is passed to the model even
  though `main.py` already filters against the Google Sheet before calling
  Claude at all. This catches near-duplicates the Sheet's exact-ID match
  can't catch (e.g. the same role appearing on two different job boards
  with two different source IDs).
- **Job list is capped, not the serialized JSON string:** `build_digest()`
  passes `jobs[:30]` into `json.dumps()` rather than truncating the
  serialized JSON string by character count. Slicing a JSON string can cut
  off mid-token and produce invalid JSON, which previously caused Claude to
  receive an unparseable `<jobs>` block and silently default to "no new
  jobs" every run.
- **Fallback formatter:** if the Anthropic API call fails for any reason
  (rate limit, network blip, billing issue), `reasoner.py` falls back to a
  deterministic Python formatter (`_fallback_format`) so a single bad API
  call doesn't silently kill that cycle's alert. It has no LLM to judge
  what's genuinely present, so it just prints whatever fields exist on each
  job dict and skips empty ones - and joins multiple jobs with the same
  `===JOB_BREAK===` delimiter so `build_digest()` splits both paths
  identically into separate messages.
