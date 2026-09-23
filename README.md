# Support Pipeline Automation
Agentic AI Challenge Iraq — Topic 06

A back-office batch pipeline (not a chatbot) that reads a queue of Iraqi-dialect
wallet support tickets and, for each one: classifies the issue, sets a
priority, extracts structured details, routes it to the right team, and
drafts a first response for a human agent to approve or edit. Anything
the pipeline isn't confident about is escalated with a reason instead of
guessed.

## 1. Architecture

```
tickets (batch) --> classify_extract() --> escalate? --------> human review queue
                                        \--> not escalated --> route + draft response --> agent approves/edits/sends
```

- **`src/lexicon.py`** — shared constants: the ticket taxonomy, routing map,
  priority rules, and the Iraqi-dialect templates/keyword lists.
- **`src/llm_client.py`** — the model layer. One function, `classify_extract()`,
  is the single entry point the pipeline calls. It tries a **live path**
  (calls the Anthropic API, model `claude-sonnet-5`) first; if no API key is
  configured or the call fails (no network, rate limit, etc.), it transparently
  falls back to a small **offline rule-based classifier** so the pipeline never
  just crashes on a batch. Every result is tagged `used_fallback` so this is
  visible downstream, not hidden.
- **`src/pipeline.py`** — orchestration: confidence threshold, "don't invent a
  required field" rule, routing table, draft assembly.
- **`src/evaluate.py`** — runs the pipeline over the held-out set and reports
  accuracy, confusion cases, field-extraction accuracy, and throughput.
- **`run_demo.py`** — CLI entry point for a live run on any judge-supplied
  batch file.

This is intentionally a thin orchestration layer around one model call per
ticket, not a multi-agent system — per the brief, "simple and reliable beats
complex," and a batch classify/extract/route/draft job doesn't need more than
that.

## 2. Iraqi Arabic handling

- All synthetic ticket data, the fallback classifier's keyword lexicon, and
  every drafted response (both the offline templates and the live-mode
  prompt) are in Iraqi dialect, not MSA or a translated tone.
- The live path sends the raw dialect text straight to Claude, which reads
  dialect natively — no translation step, no normalization.
- The offline fallback is deliberately simple (keyword + regex matching) and
  is the weaker of the two paths on dialect variation — see **Failure modes**
  below for a concrete example we hit and fixed during testing.

## 3. Data

**Method:** Claude (this repo's AI coding assistant — see Disclosure) authored
71 Iraqi-dialect ticket templates across 8 categories, covering the scenarios
named in the brief (failed transfer, wrong recipient, login problem, agent
dispute, card issue) plus three more we added for coverage (balance inquiry,
bill payment issue, general/other). `src/generate_data.py` expands each
template 3x with randomized slot-filling (names, amounts, relative dates,
mock transaction IDs, billers) and light noise phrases, producing **213
labeled tickets** — comfortably over the brief's 200 minimum. A stratified
~22% per category is held out and never used to tune keywords, thresholds, or
templates.

```
Total: 213   Dev: 165   Heldout: 48

Category              Dev / Heldout
failed_transfer         33 / 9
wrong_recipient         23 / 7
login_problem           23 / 7
agent_dispute           19 / 5
card_issue              19 / 5
balance_inquiry         16 / 5
bill_payment_issue      16 / 5
other                   16 / 5
```

A sample was read by hand during development (see the confusion-case fix in
Failure modes) to check it sounds like real customers, not templated text.

**Taxonomy:** category (8 values), priority (high/medium/low), and fields
`transaction_id`, `amount`, `date_expr`, `recipient_name`, `biller` — extracted
only when actually present in the ticket text (never invented; see Must-have
compliance below).

## 4. How to run

```bash
pip install -r requirements.txt          # only needed for live mode

# regenerate the synthetic dataset (deterministic, seed=42)
python3 src/generate_data.py

# evaluate on the held-out set
python3 src/evaluate.py

# live run on any batch of tickets (one JSON object per line, needs "text")
python3 run_demo.py data/judge_sample_input.jsonl results/judge_sample_output.jsonl
```

**To use the live LLM path** (recommended for the actual judging demo —
dialect handling and field extraction both generalize far better than the
offline fallback): `export ANTHROPIC_API_KEY=sk-...` before running. No code
changes needed; `classify_extract()` picks it up automatically and only
falls back if the call fails. This path is fully implemented but has not
been exercised end-to-end in this build sandbox, which has no network
access — test it once with a real key before the demo.

## 5. Evaluation results (held-out set, n=48)

Numbers below are a real run of the code in this repo — not hand-picked.
**They reflect the offline fallback path**, since this sandbox has no network
access to call the live API; expect the live path to do noticeably better,
especially on field extraction (see Failure modes).

| Metric | Result |
|---|---|
| Category accuracy | **87.5%** (42/48) |
| Priority accuracy | **91.7%** (44/48) |
| Escalated to human review | 30/48 (62.5%) |
| Auto-routed with a draft response | 18/48 |

**Why the escalation rate is high:** it is not mainly classifier failure.
Escalations split into low classification confidence (17 tickets) and
tickets correctly classified but missing a field the category can't be
safely actioned without — usually no amount stated (17 tickets, overlapping
with the above). That second bucket is a deliberate policy, not a bug: several
categories (failed_transfer, wrong_recipient, agent_dispute,
bill_payment_issue) require an amount before auto-routing; if the ticket text
doesn't state one, the pipeline escalates for a human to ask rather than
inventing a number. Field extraction, when a field *is* present in the gold
ticket, was 100% for the offline path (see the honest caveat about this in
Failure modes).

Full report with the confusion-case list: `results/evaluation_report.md`.
Full per-ticket demo run: `results/judge_sample_output.jsonl`.

## 6. Failure modes (documented, as required)

1. **Arabic possessive inflection breaks naive keyword matching.**
   Found during testing: the ticket *"بطاقتي انسرقت امس"* (my card was
   stolen) was misclassified as `other` because the fallback's keyword was
   "بطاقة" (card) and "بطاقتي" (my card) doesn't contain it as a substring —
   the possessive suffix changes the final letter (ة → ت). We fixed this
   specific case by adding the inflected form to the lexicon, which raised
   held-out category accuracy from 83.3% to 87.5% and priority accuracy from
   87.5% to 91.7% in one pass. But this is one instance of a general class of
   problem (Arabic has rich inflection: possessives, plurals, gender/case
   marking) that a fixed keyword list cannot fully cover — which is exactly
   why the **live LLM path is the intended production path**; a language
   model reads inflected Arabic natively instead of via a fixed vocabulary.
   **Handling:** documented and partially patched in the fallback; the
   underlying fix is using live mode for the actual demo.

2. **Low-confidence or missing-field tickets are escalated, never guessed.**
   The confidence score (margin between the top two keyword matches) and the
   critical-field check are both hard gates in `pipeline.py`. If either
   fails, `escalate=True` and `draft_response=None` — nothing is
   auto-approved or auto-sent. **Handling:** built into the pipeline's control
   flow, not a post-hoc filter; verified in the evaluation run above (30/48
   escalations, all traceable to one of these two rules).

3. **No live LLM available (no API key, no network, or the API call
   errors).** `classify_extract()` catches this and drops to the offline
   fallback rather than crashing the batch job. The tradeoff: lower accuracy
   and a much higher escalation rate (see the numbers above), which is a
   conservative, safe direction to fail in — more gets sent to a human, not
   fewer or worse ones auto-sent. `used_fallback=True` is attached to every
   such result so it's visible in the JSONL output and the run summary, not
   silently swallowed. **Handling:** implemented and exercised in every run
   in this sandbox (no network here), see `results/`.

4. **Two issues mentioned in one ticket.** E.g. `data/judge_sample_input.jsonl`
   ticket J09 mentions both a login problem and a failed transfer in the same
   message. The pipeline currently classifies by whichever category's
   keywords score higher (here: failed_transfer) rather than flagging
   "possibly multi-issue" explicitly. In this case it still escalates anyway
   (no amount stated), so the outcome is safe, but the reason given is
   generic rather than "multi-issue." **Handling:** not fully solved —
   flagged here as a known limitation and a good next increment (an explicit
   multi-issue flag when two categories' scores are within a small margin of
   each other, or, in live mode, asking the model directly).

## 7. Disclosure

- **Models:** Claude (Anthropic) — used both as the AI coding assistant that
  wrote this entire codebase (pipeline, data generator, evaluation harness,
  this README) and as the intended runtime model (`claude-sonnet-5` via the
  Anthropic Messages API) for the live classify/extract/draft path.
- **Data:** 100% synthetic, generated as described in section 3. No real
  customer records, identity documents, or transaction histories were used
  or seen.
- **Libraries:** Python 3 standard library only, plus the `anthropic` SDK
  (only imported/required for the live path — the offline fallback has zero
  third-party dependencies).
- **Tools:** built and tested in a sandboxed environment with no network
  access, which is why every number in this README is from the offline
  fallback path and the live path is implemented-but-unverified end-to-end
  (see section 4).

## 8. Out of scope (per the brief)

Not a customer-facing chatbot — batch pipeline only. No drafted response is
ever sent automatically; a human always approves. No real ticket data, real
customers, or real routing systems are touched.

## 9. Before you submit

- **Git history:** this deliverable was generated in one session, so there is
  no commit history spanning a real build period yet — that's a hard
  requirement for judging ("A repository with commit history spanning the
  build period"). `git init` this folder and commit your own changes as you
  extend and customize it; don't backdate commits to fake a history.
- **Verify live mode once** with a real `ANTHROPIC_API_KEY` and network
  access before the judges' demo — it's coded correctly against the
  documented API shape but has literally never made a real network call
  in this sandbox.
- Good next increments if you have time: per-category precision/recall (not
  just overall accuracy), confidence calibration check on live mode, the
  multi-issue flag from Failure mode 4, and the brief's stretch goal (a
  weekly pattern report).
