# -*- coding: utf-8 -*-
"""
Two classify/extract/draft implementations behind one interface:

  1. Live path (classify_extract_live / draft_response_live): calls the
     Anthropic API (model: claude-sonnet-5). This is the intended
     production path — an LLM reading the raw Iraqi-dialect ticket
     natively, which is what should run for the judges' live demo.

  2. Offline fallback (classify_fallback / extract_fields_fallback /
     draft_response_fallback): a small keyword + regex baseline used
     only when ANTHROPIC_API_KEY isn't set or the API call fails
     (e.g. no network, as in this build sandbox). It is deliberately
     conservative — see README "Failure modes".

classify_extract() is the single entry point the pipeline calls; it
tries the live path first and transparently falls back, tagging the
result with used_fallback so that's visible downstream and in reports.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import lexicon

MODEL = "claude-sonnet-5"
CATEGORIES = list(lexicon.TEMPLATES.keys())

AMOUNT_RE = re.compile(r"(\d+)\s*الف")
TXN_RE = re.compile(r"\bTXN\d+\b")


# --------------------------------------------------------------------
# Offline fallback: classification
# --------------------------------------------------------------------
def classify_fallback(text):
    scores = {}
    for cat, kws in lexicon.CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if kw in text)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_cat, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score == 0:
        return "other", 0.35

    margin = top_score - second_score
    confidence = min(0.95, 0.5 + 0.15 * margin)
    return top_cat, round(confidence, 2)


# --------------------------------------------------------------------
# Offline fallback: field extraction
# --------------------------------------------------------------------
def extract_fields_fallback(text):
    amount_m = AMOUNT_RE.search(text)
    txn_m = TXN_RE.search(text)

    date_found = next((d for d in lexicon.REL_DATES if d in text), None)
    name_found = next((n for n in lexicon.NAMES if n in text), None)
    biller_found = next((b for b in lexicon.BILLERS if b in text), None)

    return {
        "transaction_id": txn_m.group(0) if txn_m else None,
        "amount": amount_m.group(1) if amount_m else None,
        "date_expr": date_found,
        "recipient_name": name_found,
        "biller": biller_found,
    }


# --------------------------------------------------------------------
# Offline fallback: drafted first response (Iraqi dialect, per category)
# --------------------------------------------------------------------
def draft_response_fallback(category, fields):
    amount_part = f" بمبلغ {fields.get('amount')} الف دينار" if fields.get("amount") else ""
    txn_part = f" (رقم العملية {fields.get('transaction_id')})" if fields.get("transaction_id") else ""
    biller = fields.get("biller") or "الفاتورة"

    if category == "failed_transfer":
        return f"شكراً لتواصلك معنا. نتحرى عملية التحويل{amount_part}{txn_part} حالياً وبنرجعلك بالنتيجة خلال 24 ساعة."
    if category == "wrong_recipient":
        return f"نتفهم انزعاجك. نراجع طلب استرجاع المبلغ{amount_part} المحول بالخطأ ونتواصل معك خلال 24 ساعة بخصوص امكانية الاسترجاع."
    if category == "login_problem":
        return "نعتذر عن الازعاج. نراجع مشكلة الدخول لحسابك حالياً، رجاءً جرب تحديث التطبيق وراسلنا اذا استمرت المشكلة."
    if category == "agent_dispute":
        return f"استلمنا بلاغك بخصوص العملية مع الوكيل{txn_part}. راح نراجع السجل ونرجعلك بالنتيجة خلال 24 ساعة."
    if category == "card_issue":
        return "نتفهم المشكلة، راح نراجع حالة بطاقتك ونرجعلك بالتفاصيل قريباً."
    if category == "balance_inquiry":
        return "راح نجهزلك التفاصيل المطلوبة عن رصيدك وحركاتك الاخيرة."
    if category == "bill_payment_issue":
        return f"نتحرى حالة دفع فاتورة {biller}{amount_part} حالياً وبنأكدلك خلال وقت قصير."
    return "استلمنا استفسارك وراح نرجعلك بالجواب المناسب قريباً."


# --------------------------------------------------------------------
# Live path (Anthropic API) — requires ANTHROPIC_API_KEY + network
# --------------------------------------------------------------------
def is_live_configured():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _live_client():
    import anthropic  # deferred import: package only required for live mode
    return anthropic.Anthropic()


LIVE_SYSTEM_PROMPT = (
    "انت جزء من نظام تصنيف تذاكر دعم لمحفظة الكترونية عراقية. تجيك رسالة عميل "
    "بالعامية العراقية وتحتاج تحلللها. رد حصرا بصيغة JSON صحيحة بدون اي نص اضافي، "
    "بهذا الشكل بالضبط:\n"
    '{"category": "<one of: ' + ", ".join(CATEGORIES) + '>", '
    '"priority": "<high|medium|low>", "confidence": <0.0-1.0>, '
    '"fields": {"transaction_id": <string or null>, "amount": <string or null>, '
    '"date_expr": <string or null>, "recipient_name": <string or null>, "biller": <string or null>}}\n'
    "استخرج الحقول فقط اذا موجودة صراحة بنص الرسالة. لا تخترع قيمة لحقل غير مذكور."
)


def classify_extract_live(text):
    client = _live_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=LIVE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[4:] if raw.lower().startswith("json") else raw
    data = json.loads(raw)
    return data


def draft_response_live(text, category, fields):
    client = _live_client()
    prompt = (
        f"اكتب رد اول قصير (سطرين كحد اقصى) بالعامية العراقية، بلهجة مهنية "
        f"ومتعاطفة، يرسله موظف دعم لعميل بخصوص هذه التذكرة (تصنيف: {category}).\n"
        f"نص التذكرة: {text}\n"
        f"لا تخترع تفاصيل غير موجودة بالتذكرة او بهذه الحقول: {json.dumps(fields, ensure_ascii=False)}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


# --------------------------------------------------------------------
# Unified entry point used by the pipeline
# --------------------------------------------------------------------
def classify_extract(text):
    if is_live_configured():
        try:
            data = classify_extract_live(text)
            data["used_fallback"] = False
            try:
                data["draft_response"] = draft_response_live(text, data["category"], data["fields"])
            except Exception:
                data["draft_response"] = None
            return data
        except Exception:
            pass  # network / API error -> fall through to offline mode

    category, confidence = classify_fallback(text)
    fields = extract_fields_fallback(text)
    priority = lexicon.PRIORITY_BASE.get(category, "low")
    amt = fields.get("amount")
    if amt and int(amt) >= 200:
        priority = "high"
    priority = lexicon.apply_priority_overrides(category, text, priority)

    return {
        "category": category,
        "confidence": confidence,
        "priority": priority,
        "fields": fields,
        "used_fallback": True,
        "draft_response": None,  # pipeline fills this via draft_response_fallback
    }
