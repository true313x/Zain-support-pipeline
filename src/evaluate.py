# -*- coding: utf-8 -*-
"""
Runs the pipeline over data/tickets_heldout.jsonl (never used to write
templates, keywords, or thresholds) and reports category accuracy,
priority accuracy, field-extraction accuracy, confusion cases, and
throughput. Writes results/evaluation_report.md.

Usage: python3 src/evaluate.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import process_batch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELD_KEYS = ["transaction_id", "amount", "date_expr", "recipient_name", "biller"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    heldout = load_jsonl(os.path.join(HERE, "data", "tickets_heldout.jsonl"))
    results, summary = process_batch([{"id": r["id"], "text": r["text"]} for r in heldout])
    gold_by_id = {r["id"]: r for r in heldout}

    correct_cat = correct_pri = 0
    confusion = collections.Counter()
    field_correct = collections.Counter()
    field_total = collections.Counter()
    confusion_examples = {}
    escalation_reasons = collections.Counter()

    for res in results:
        gold = gold_by_id[res.ticket_id]

        if res.escalate:
            if "low classification confidence" in (res.escalate_reason or ""):
                escalation_reasons["low confidence"] += 1
            if "missing required field" in (res.escalate_reason or ""):
                escalation_reasons["missing critical field (won't guess an amount)"] += 1

        if res.category == gold["category"]:
            correct_cat += 1
        else:
            key = (gold["category"], res.category)
            confusion[key] += 1
            if key not in confusion_examples:
                confusion_examples[key] = gold["text"]

        if res.priority == gold["priority"]:
            correct_pri += 1

        for fkey in FIELD_KEYS:
            gold_val = gold["fields"].get(fkey)
            if gold_val is None:
                continue
            field_total[fkey] += 1
            pred_val = getattr(res.fields, fkey)
            if pred_val is not None and str(pred_val) == str(gold_val):
                field_correct[fkey] += 1

    n = len(results)
    cat_acc = correct_cat / n
    pri_acc = correct_pri / n
    escalated = summary["escalated"]

    lines = []
    lines.append(f"# Evaluation Report — held-out set (n={n}, never tuned on)\n")
    lines.append("Run with no live LLM available in this sandbox (no network) — "
                  "all predictions below are from the offline rule-based fallback "
                  "classifier. See README for the live-mode path.\n")
    lines.append("## Headline numbers")
    lines.append(f"- Category classification accuracy: **{cat_acc:.1%}** ({correct_cat}/{n})")
    lines.append(f"- Priority accuracy: **{pri_acc:.1%}** ({correct_pri}/{n})")
    lines.append(f"- Escalated to human review: **{escalated}/{n} ({escalated/n:.1%})**")
    lines.append(f"- Auto-routed with a draft response: {n - escalated}/{n}\n")

    lines.append("## Why tickets were escalated (a ticket can hit more than one reason)")
    for reason, cnt in escalation_reasons.most_common():
        lines.append(f"- {reason}: {cnt}")
    lines.append("")

    lines.append("## Field extraction accuracy (exact match, only scored when the field is present in gold)")
    for fkey in FIELD_KEYS:
        tot = field_total[fkey]
        if tot:
            acc = field_correct[fkey] / tot
            lines.append(f"- {fkey}: {acc:.1%} ({field_correct[fkey]}/{tot})")
        else:
            lines.append(f"- {fkey}: n/a (not present in any held-out gold ticket)")

    lines.append("\n## Confusion cases (gold category -> predicted category)")
    if confusion:
        for (g, p), c in confusion.most_common():
            example = confusion_examples[(g, p)]
            lines.append(f"- **{g} -> {p}** ({c} case{'s' if c > 1 else ''}). Example: \u201c{example}\u201d")
    else:
        lines.append("- None — every held-out ticket was classified into the correct category.")

    lines.append("\n## Throughput")
    lines.append(f"- Tickets processed: {n}")
    lines.append(f"- Auto-routed (not escalated): {n - escalated}")
    lines.append(f"- Escalated to human review: {escalated}")
    lines.append("\n## By category (held-out set)")
    for cat, cnt in summary["by_category"].items():
        lines.append(f"- {cat}: {cnt} predicted")

    report = "\n".join(lines) + "\n"

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "evaluation_report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    main()
