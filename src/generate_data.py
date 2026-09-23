# -*- coding: utf-8 -*-
"""
Generates the synthetic Iraqi-dialect support ticket dataset.

Method: Claude authored the Iraqi-dialect templates in lexicon.py
(one per realistic support scenario per category). This script expands
them into a full labeled dataset via randomized slot-filling (names,
amounts, dates, transaction ids, billers) plus light noise phrases,
then holds back a stratified per-category slice as a held-out test
set the pipeline is never tuned on.

Usage: python3 src/generate_data.py
Writes: data/tickets_dev.jsonl, data/tickets_heldout.jsonl
"""
import json
import os
import random
import string
import sys

sys.path.insert(0, os.path.dirname(__file__))
import lexicon

random.seed(42)

VARIANTS_PER_TEMPLATE = 3
HELDOUT_FRACTION = 0.22


def rand_amount():
    return str(random.choice(lexicon.AMOUNTS_THOUSANDS))


def rand_txn():
    return "TXN" + "".join(random.choice(string.digits) for _ in range(6))


def rand_slots():
    return {
        "amount": rand_amount(),
        "name": random.choice(lexicon.NAMES),
        "name2": random.choice(lexicon.NAMES),
        "date": random.choice(lexicon.REL_DATES),
        "txn": rand_txn(),
        "biller": random.choice(lexicon.BILLERS),
    }


def slots_used(template):
    return set(fn for _, fn, _, _ in string.Formatter().parse(template) if fn)


def gold_priority(category, amount_thousands, text):
    p = lexicon.PRIORITY_BASE[category]
    if amount_thousands is not None and amount_thousands >= 200 and p != "high":
        p = "high"
    p = lexicon.apply_priority_overrides(category, text, p)
    return p


def make_ticket(tid, category, template):
    used = slots_used(template)
    slots = rand_slots()
    text = template.format(**slots)

    if random.random() < 0.5:
        text = random.choice(lexicon.NOISE_PREFIX) + text
    if random.random() < 0.35:
        text = text + random.choice(lexicon.NOISE_SUFFIX)

    amount_thousands = int(slots["amount"]) if "amount" in used else None
    fields = {
        "transaction_id": slots["txn"] if "txn" in used else None,
        "amount": slots["amount"] if "amount" in used else None,
        "date_expr": slots["date"] if "date" in used else None,
        "recipient_name": slots["name"] if "name" in used else None,
        "biller": slots["biller"] if "biller" in used else None,
    }
    priority = gold_priority(category, amount_thousands, text)

    return {
        "id": tid,
        "text": text.strip(),
        "category": category,
        "priority": priority,
        "fields": fields,
        "team": lexicon.ROUTING[category],
    }


def main():
    records = []
    tid = 1
    for category, templates in lexicon.TEMPLATES.items():
        for template in templates:
            for _ in range(VARIANTS_PER_TEMPLATE):
                records.append(make_ticket(f"T{tid:04d}", category, template))
                tid += 1

    by_cat = {}
    for r in records:
        by_cat.setdefault(r["category"], []).append(r)

    dev, heldout = [], []
    for cat, items in by_cat.items():
        random.shuffle(items)
        n_heldout = max(4, round(len(items) * HELDOUT_FRACTION))
        heldout.extend(items[:n_heldout])
        dev.extend(items[n_heldout:])

    random.shuffle(dev)
    random.shuffle(heldout)

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(here, "data")
    os.makedirs(data_dir, exist_ok=True)

    with open(os.path.join(data_dir, "tickets_dev.jsonl"), "w", encoding="utf-8") as f:
        for r in dev:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(data_dir, "tickets_heldout.jsonl"), "w", encoding="utf-8") as f:
        for r in heldout:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Total tickets: {len(records)}")
    print(f"Dev: {len(dev)}   Heldout: {len(heldout)}")
    print("\nPer-category counts (dev / heldout):")
    for cat in lexicon.TEMPLATES:
        d = sum(1 for r in dev if r["category"] == cat)
        h = sum(1 for r in heldout if r["category"] == cat)
        print(f"  {cat:20s} {d:3d} / {h:3d}")

    print("\nSample tickets (hand-check for realism):")
    for r in records[:6]:
        print(f"  [{r['category']}/{r['priority']}] {r['text']}")


if __name__ == "__main__":
    main()
