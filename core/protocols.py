#!/usr/bin/env python3
"""protocols.py — the outbound decision cascade: protocol → precedent → exploration.

Given a surfaced obligation (a "fire" row: sender, subject, label, tier), derive the
KNOWN NEXT STEP without a network call or an LLM. Three rungs, tried in order:

    1. PROTOCOL    — a recurring class with a codified next step + draft intent
                     (loan-default, billing-decline, fraud-alert, kyc, legal-sign …).
    2. PRECEDENT   — no protocol, but a real human / known correspondent → reply by
                     precedent (a person who wrote you is owed a human reply).
    3. EXPLORATION — unknown → a research/verify next step until the action is certain.

This module only DECIDES the rung and emits the concrete, owned next step (+ an
optional draft intent). It never sends or mutates mail. The hard ideal-form synthesis
for the actual reply text — when protocol+precedent are silent — is left to a keyless
``claude -p`` pass downstream; this is the deterministic spine that says which rung
applies and what the human's single next move is.

Design notes:
- Every obligation is owned by HIM ("yours") — the system surfaces, it never acts.
- `verify` marks a class that is phishing-prone (fraud/credential-change notices): the
  next step leads with "confirm the sender is real" before any action, so a spoof can
  never steer a real action. The raw display name never drives the decision.
- Priorities are derived from consequence (money/legal/security > infra > marketing),
  not from the sender's brand — a generic "payment failed" outranks a recruiter.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Obligation:
    """One derived next-step for a surfaced fire. Provenance (account/id) is attached
    by the builder; this is the decision layer."""
    cls: str                       # protocol class id (or "precedent"/"exploration")
    rung: str                      # "protocol" | "precedent" | "exploration"
    priority: int                  # 0–100, by consequence
    next_step: str                 # the single concrete move he makes
    why: str                       # one line: which rung fired and on what signal
    owner: str = "yours"
    verify_first: bool = False     # phishing-prone → confirm sender before acting
    requires_reply: bool = False   # is a human/outbound reply owed?
    draft_hint: Optional[str] = None  # seed intent for a draft-only writer (never sent)
    tags: List[str] = field(default_factory=list)


def _addr(sender: str) -> str:
    return (sender.split("<")[-1].rstrip(">").strip().lower()
            if "<" in sender else (sender or "").strip().lower())


def _looks_human(sender: str) -> bool:
    """A real person, not a role/brand mailbox. Mirrors inbox_sweep.looks_human but kept
    local so this module is import-free and reusable headless."""
    addr = _addr(sender)
    role = ("noreply", "no-reply", "donotreply", "do-not-reply", "notification",
            "notifications", "alert", "alerts", "support", "info", "hello", "team",
            "news", "marketing", "auto", "mailer", "updates", "account", "billing",
            "service", "services", "reply", "sales", "contact", "admin", "store",
            "order", "payments", "reviews", "feedback", "survey", "invoice", "notify")
    if any(k in addr for k in role):
        return False
    name = (sender or "").split("<")[0].strip().strip('"')
    parts = [p for p in re.split(r"\s+", name) if p]
    brandish = any(b in name.lower() for b in
                   ("via", "inc", "llc", "bank", "card", "health", "deals", "store",
                    "finance", "co.", "labs", "group", "platform", "pbc"))
    return len(parts) >= 2 and not name.isupper() and "@" not in name and not brandish


# Each protocol: a class id, a matcher over "sender subject snippet", a consequence
# priority, the codified next step, whether it needs sender-verification first, whether
# a reply is owed, and a draft intent (None = no outbound reply, just an action).
# Order matters: most-consequential / most-specific first (first match wins).
_PROTOCOLS = [
    {
        "cls": "security-credential-change",
        "match": re.compile(r"(?ix) (fsa\s*id|password|sign[-\s]*in|login\s*code|"
                            r"allowed .*access|access to .*account|was changed|"
                            r"recovery|2fa|two[-\s]*factor|verification code)"),
        "priority": 95, "verify_first": True, "requires_reply": False,
        "next_step": "VERIFY you made this change. If NOT you: secure the account "
                     "immediately (change password, revoke sessions/third-party access).",
        "draft_hint": None,
        "tags": ["security"],
    },
    {
        "cls": "fraud-alert",
        "match": re.compile(r"(?ix) (fraud|unauthorized|unrecognized|suspicious|"
                            r"did you (make|try)|confirm you|security alert|locked)"),
        "priority": 90, "verify_first": True, "requires_reply": False,
        "next_step": "VERIFY the sender is genuine (fraud notices are heavily spoofed — "
                     "do NOT click links). If real, call the number on the back of the card.",
        "draft_hint": None,
        "tags": ["security", "money"],
    },
    {
        "cls": "loan-default",
        "match": re.compile(r"(?ix) (nelnet|studentaid|student\s*loan|fsa\b|"
                            r"default|garnish|wage|recertif|repayment plan|"
                            r"federal student aid)"),
        "priority": 88, "verify_first": False, "requires_reply": False,
        "next_step": "Log in at nelnet.studentaid.gov: check default status, recertify "
                     "the income-driven repayment plan, and set the lowest viable payment.",
        "draft_hint": None,
        "tags": ["money", "gov"],
    },
    {
        "cls": "billing-decline",
        "match": re.compile(r"(?ix) (payment (was )?(unsuccessful|declined|failed)|"
                            r"problem billing|billing problem|couldn.?t charge|"
                            r"unable to charge|past[-\s]*due|overdue|outstanding balance|"
                            r"access .*paused|subscription .*paused|update your (payment|"
                            r"information|card)|charge the credit card)"),
        "priority": 82, "verify_first": False, "requires_reply": False,
        "next_step": "Root cause is the card-0186 hold — resolve THAT first, then update "
                     "the payment method here. (Cascades to Anthropic / Google Cloud / GitHub.)",
        "draft_hint": None,
        "tags": ["money", "card-0186"],
    },
    {
        "cls": "kyc",
        "match": re.compile(r"(?ix) (kyc|verify your (identity|business)|stripe|"
                            r"take action to keep|keep things running|tax (id|info)|"
                            r"w-?9|onboarding|verification (required|needed))"),
        "priority": 78, "verify_first": False, "requires_reply": False,
        "next_step": "Provide the exact info requested. Note: Stripe KYC is blocked on the "
                     "dead LLC — prefer the individual monetization rail (Ko-fi/Lemon Squeezy).",
        "draft_hint": None,
        "tags": ["money", "product"],
    },
    {
        "cls": "legal-sign",
        "match": re.compile(r"(?ix) (docusign|sign(ed)? (this|the|a )?(document|proposal)|"
                            r"review and sign|mediation|mediator|settlement|proposal\.pdf|"
                            r"complete with docusign)"),
        "priority": 80, "verify_first": False, "requires_reply": False,
        "next_step": "Read the document fully before signing (legal). Sign only if the "
                     "terms are correct; otherwise note the objection and reply.",
        "draft_hint": None,
        "tags": ["legal"],
    },
    {
        "cls": "legal-correspondence",
        "match": re.compile(r"(?ix) (protected message|litigation|attorney|counsel|"
                            r"senator|government accountability|legal (unit|matter)|"
                            r"consent form|on behalf of)"),
        "priority": 68, "verify_first": False, "requires_reply": True,
        "next_step": "Read the message. If a response is owed, reply concisely confirming "
                     "receipt and the next channel/timeline.",
        "draft_hint": "Acknowledge receipt, confirm the next step or channel, keep it brief "
                      "and professional.",
        "tags": ["legal"],
    },
    {
        "cls": "registered-agent",
        "match": re.compile(r"(?ix) (legalzoom|registered agent|resign as your|"
                            r"reinstate|annual report|stay compliant)"),
        "priority": 58, "verify_first": False, "requires_reply": False,
        "next_step": "Decide: renew the registered agent OR let the LLC lapse "
                     "(the LLCs are dead — lapsing is likely correct, but confirm no live filing).",
        "draft_hint": None,
        "tags": ["money", "legal"],
    },
    {
        "cls": "domain-renewal",
        "match": re.compile(r"(?ix) (renew to keep|domain .*(expir|renew)|"
                            r"expiring soon|auto[-\s]*renew)"),
        "priority": 48, "verify_first": False, "requires_reply": False,
        "next_step": "Decide which domains are worth keeping; renew those, let the rest lapse.",
        "draft_hint": None,
        "tags": ["infra"],
    },
    {
        "cls": "infra-alarm",
        "match": re.compile(r"(?ix) (workers kv|free tier limit|routines? .*(paused|"
                            r"limit)|daily limit reached|cloud shell|deletion notice|"
                            r"quota|rate limit)"),
        "priority": 32, "verify_first": False, "requires_reply": False,
        "next_step": "Your own infra signal — the system self-heals. No action unless you "
                     "want to raise the limit / preserve the resource.",
        "draft_hint": None,
        "tags": ["infra", "self"],
    },
    {
        "cls": "app-update",
        "match": re.compile(r"(?ix) (update .*(app|macos)|security update for|"
                            r"please update any)"),
        "priority": 28, "verify_first": False, "requires_reply": False,
        "next_step": "Update the app if still in use; otherwise ignore (low risk, often "
                     "past deadline).",
        "draft_hint": None,
        "tags": ["maintenance"],
    },
]


def derive(sender: str, subject: str, label: str = "", tier: int = 4,
           snippet: str = "") -> Obligation:
    """Run the cascade for one surfaced fire and return its owned next step."""
    hay = f"{sender} {subject} {snippet} {label}"

    for p in _PROTOCOLS:
        if p["match"].search(hay):
            return Obligation(
                cls=p["cls"], rung="protocol", priority=p["priority"],
                next_step=p["next_step"], why=f"protocol:{p['cls']} matched the subject/sender",
                verify_first=p["verify_first"], requires_reply=p["requires_reply"],
                draft_hint=p["draft_hint"], tags=list(p["tags"]),
            )

    # Rung 2 — PRECEDENT: a real human wrote; a person is owed a human reply.
    if _looks_human(sender):
        return Obligation(
            cls="precedent", rung="precedent", priority=45,
            next_step="A real person wrote you — read and reply by precedent (match your "
                      "prior tone with this correspondent).",
            why="precedent: sender looks like a real human, no protocol matched",
            requires_reply=True,
            draft_hint="Reply in your own voice; answer their question or set the next step.",
            tags=["human"],
        )

    # Rung 3 — EXPLORATION: unknown signal → research until the action is certain.
    return Obligation(
        cls="exploration", rung="exploration", priority=35,
        next_step="Open and determine the required action (no protocol or precedent "
                  "matched — verify what, if anything, is owed).",
        why="exploration: no protocol or precedent matched",
        requires_reply=False,
        tags=["unknown"],
    )
