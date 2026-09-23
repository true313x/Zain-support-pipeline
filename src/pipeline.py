# -*- coding: utf-8 -*-
"""
Support Pipeline Automation — core logic.

For each ticket: classify -> set priority -> extract structured fields
-> route to a team -> draft a first response. Anything below the
confidence bar, or missing a field the category can't be actioned
without, is escalated to a human instead of guessed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from schema import ExtractedFields, PipelineResult
import llm_client
import lexicon

CONFIDENCE_THRESHOLD = 0.55
FIELD_KEYS = ["transaction_id", "amount", "date_expr", "recipient_name", "biller"]


def process_ticket(ticket):
    data = llm_client.classify_extract(ticket["text"])

    category = data["category"]
    confidence = data["confidence"]
    priority = data["priority"]
    fields_dict = data["fields"]
    used_fallback = data["used_fallback"]

    fields = ExtractedFields(**{k: fields_dict.get(k) for k in FIELD_KEYS})
    team = lexicon.ROUTING.get(category, "General Queue")

    reasons = []
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append("low classification confidence")

    critical = lexicon.CRITICAL_FIELD.get(category)
    if critical and getattr(fields, critical) is None:
        reasons.append(f"missing required field: {critical}")

    escalate = bool(reasons)
    reason = "; ".join(reasons) if reasons else None

    draft = None
    if not escalate:
        draft = data.get("draft_response")
        if not draft:
            draft = llm_client.draft_response_fallback(category, fields_dict)

    return PipelineResult(
        ticket_id=ticket["id"],
        text=ticket["text"],
        category=category,
        confidence=confidence,
        priority=priority,
        fields=fields,
        team=team,
        escalate=escalate,
        escalate_reason=reason,
        draft_response=draft,
        used_fallback=used_fallback,
    )


def process_batch(tickets):
    results = [process_ticket(t) for t in tickets]
    summary = {
        "total": len(results),
        "escalated": sum(1 for r in results if r.escalate),
        "used_fallback": sum(1 for r in results if r.used_fallback),
        "by_category": {},
        "by_team": {},
    }
    for r in results:
        summary["by_category"][r.category] = summary["by_category"].get(r.category, 0) + 1
        summary["by_team"][r.team] = summary["by_team"].get(r.team, 0) + 1
    return results, summary
