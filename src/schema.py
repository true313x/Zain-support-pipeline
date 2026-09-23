# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedFields:
    transaction_id: Optional[str] = None
    amount: Optional[str] = None
    date_expr: Optional[str] = None
    recipient_name: Optional[str] = None
    biller: Optional[str] = None

    def as_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "date_expr": self.date_expr,
            "recipient_name": self.recipient_name,
            "biller": self.biller,
        }


@dataclass
class PipelineResult:
    ticket_id: str
    text: str
    category: str
    confidence: float
    priority: str
    fields: ExtractedFields
    team: str
    escalate: bool
    escalate_reason: Optional[str]
    draft_response: Optional[str]
    used_fallback: bool
