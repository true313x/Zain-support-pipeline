# Evaluation Report — held-out set (n=48, never tuned on)

Run with no live LLM available in this sandbox (no network) — all predictions below are from the offline rule-based fallback classifier. See README for the live-mode path.

## Headline numbers
- Category classification accuracy: **87.5%** (42/48)
- Priority accuracy: **91.7%** (44/48)
- Escalated to human review: **30/48 (62.5%)**
- Auto-routed with a draft response: 18/48

## Why tickets were escalated (a ticket can hit more than one reason)
- missing critical field (won't guess an amount): 17
- low confidence: 17

## Field extraction accuracy (exact match, only scored when the field is present in gold)
- transaction_id: 100.0% (2/2)
- amount: 100.0% (11/11)
- date_expr: 100.0% (9/9)
- recipient_name: 100.0% (10/10)
- biller: 100.0% (5/5)

## Confusion cases (gold category -> predicted category)
- **login_problem -> other** (2 cases). Example: “من فضلكم نزلت التطبيق بجهاز جديد وما گدرت استرجع حسابي القديم”
- **card_issue -> failed_transfer** (1 case). Example: “طلبت بطاقة جديدة من مدة وليحد هسة ما وصلتني”
- **balance_inquiry -> other** (1 case). Example: “ارجوكم ودي اعرف تفاصيل اخر خمس عمليات سويتها شنو الحل لو سمحتوا؟”
- **agent_dispute -> failed_transfer** (1 case). Example: “عندي خلاف مع وكيل، يدعي اني ما دفعت له رغم عندي اثبات تحويل TXN472779 شنو الحل لو سمحتوا؟”
- **wrong_recipient -> other** (1 case). Example: “دزيت 40 الف دينار عن طريق الخطأ لشخص مب اعرفه، ساعدوني استرد المبلغ”

## Throughput
- Tickets processed: 48
- Auto-routed (not escalated): 18
- Escalated to human review: 30

## By category (held-out set)
- failed_transfer: 11 predicted
- login_problem: 5 predicted
- card_issue: 4 predicted
- other: 9 predicted
- agent_dispute: 4 predicted
- wrong_recipient: 6 predicted
- balance_inquiry: 4 predicted
- bill_payment_issue: 5 predicted
