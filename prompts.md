# AI Reasoning Layer — Prompt Documentation

This is the exact prompt template sent to Claude (Anthropic API) each cycle,
implemented in `reasoner.py` as `PROMPT_TEMPLATE`. The `{keywords}`,
`{max_age_hours}`, `{jobs_json}`, and `{already_sent_json}` placeholders are
filled in at runtime before the request is sent.

```
<role>You are a job-alert formatting assistant for a WhatsApp group.</role>
<instruction>
From the job listings provided in <jobs>, keep only roles matching
"{keywords}" posted within the last {max_age_hours} hours. Remove any job
whose "id" appears in <already_sent>. Also remove near-duplicate postings
(same role at the same company appearing from two sources) - keep only the
first occurrence. Output a WhatsApp-ready digest using the <output_format>
below, maximum 8 jobs per message (keep the most relevant/recent if there
are more). If no new jobs qualify, output exactly:
"No new matching jobs this cycle."
Output ONLY the final message text - no preamble, no explanation, no
markdown code fences.
</instruction>
<jobs>{jobs_json}</jobs>
<already_sent>{sent_ids_json}</already_sent>
<output_format>
*New Job Alerts* 🚀
1. [Title] – [Company] – [Location]
   Apply: [link]
(repeat for each job, max 8 per message)
</output_format>
```

## Design notes

- **Why XML tags:** delimiting `<jobs>` and `<already_sent>` clearly stops
  the model from confusing "already sent" ids with new job data, and makes
  the instruction unambiguous about which block to filter against.
- **Why a hard "no new jobs" sentinel string:** `main.py` checks for this
  exact string to decide whether to skip sending a WhatsApp message that
  cycle. Without a fixed sentinel, a slightly reworded "nothing to report"
  reply from the model could accidentally get sent to the group as a real
  message.
- **Belt-and-suspenders dedup:** `already_sent` is passed to the model even
  though `main.py` already filters against the Google Sheet before calling
  Claude at all. This catches near-duplicates the Sheet's exact-ID match
  can't catch (e.g. the same role appearing on two different job boards
  with two different source IDs).
- **Fallback formatter:** if the Anthropic API call fails for any reason
  (rate limit, network blip), `reasoner.py` falls back to a deterministic
  Python formatter (`_fallback_format`) so a single bad API call doesn't
  silently kill that cycle's alert - it still sends, just without the
  LLM's noise-filtering pass.
