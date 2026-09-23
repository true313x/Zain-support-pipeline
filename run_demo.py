# -*- coding: utf-8 -*-
"""
Live-run entry point: point this at any batch of tickets (one JSON
object per line, each with at least a "text" field, or a plain .txt
file with one ticket per line) and it runs the full pipeline over the
batch and writes the per-ticket results plus a summary.

Usage:
    python3 run_demo.py data/judge_sample_input.jsonl
    python3 run_demo.py data/judge_sample_input.jsonl results/my_output.jsonl
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from pipeline import process_batch


def load_input(path):
    tickets = []
    with open(path, encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                tickets.append({"id": obj.get("id", f"IN{len(tickets) + 1}"), "text": obj["text"]})
        else:
            for i, line in enumerate(f):
                line = line.strip()
                if line:
                    tickets.append({"id": f"IN{i + 1}", "text": line})
    return tickets


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_demo.py <tickets_file.jsonl|.txt> [output.jsonl]")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "results/demo_output.jsonl"

    tickets = load_input(in_path)
    results, summary = process_batch(tickets)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({
                "id": r.ticket_id,
                "text": r.text,
                "category": r.category,
                "confidence": r.confidence,
                "priority": r.priority,
                "team": r.team,
                "fields": r.fields.as_dict(),
                "escalate": r.escalate,
                "escalate_reason": r.escalate_reason,
                "draft_response": r.draft_response,
                "used_fallback": r.used_fallback,
            }, ensure_ascii=False) + "\n")

    print(f"Processed {summary['total']} tickets — "
          f"{summary['escalated']} escalated to human review, "
          f"{summary['total'] - summary['escalated']} auto-routed with a draft response.")
    if summary["used_fallback"]:
        print(f"(offline fallback classifier used for {summary['used_fallback']}/{summary['total']} "
              f"tickets — no live LLM available)")

    print("\nBy category:")
    for cat, cnt in sorted(summary["by_category"].items(), key=lambda kv: -kv[1]):
        print(f"  {cat}: {cnt}")

    print("\nBy team:")
    for team, cnt in sorted(summary["by_team"].items(), key=lambda kv: -kv[1]):
        print(f"  {team}: {cnt}")

    print(f"\nPer-ticket results written to {out_path}")


if __name__ == "__main__":
    main()
