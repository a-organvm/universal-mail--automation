#!/usr/bin/env python3
"""unsubscribe.py — propose-mode noise killers: stop the inbox refilling at the source.

Reliable unsubscribe / Gmail-filter creation needs a write door (the Gmail filters API or
the one-click ``List-Unsubscribe`` HTTPS POST — both gated on L-MCP / L-OAUTH /
L-IMAP-APP-PW). Until one opens, this runs in PROPOSE mode: from the already-classified
sweep receipts it finds the senders that keep REFILLING the inbox with noise (archived
again and again), ranks them by how loudly they recur, and emits the exact owned action —
"unsubscribe / filter <sender>" — so the value is captured and visible, never a silent
gap ([[no-never-happens-again]]). When a write door opens, each proposal becomes a one-tap
execution with no rework.

Also provides ``parse_list_unsubscribe`` for the header path (used once message headers are
available), extracting the mailto: and HTTPS one-click variants per RFC 2369 / RFC 8058.
"""

import re
from collections import defaultdict

_GATED_ON = "L-MCP / L-OAUTH / L-IMAP-APP-PW"


def _addr(sender: str) -> str:
    return (sender.split("<")[-1].rstrip(">").strip().lower()
            if "<" in sender else (sender or "").strip().lower())


def _domain(sender: str) -> str:
    return _addr(sender).split("@")[-1] or "(none)"


def _name(sender: str) -> str:
    name = (sender or "").split("<")[0].strip().strip('"')
    return name if name and "@" not in name else _domain(sender)


def parse_list_unsubscribe(header: str):
    """Parse a List-Unsubscribe header into its actionable targets.

    Returns {"mailto": [...], "https": [...]}. Prefer the HTTPS one-click target (RFC
    8058) when a ``List-Unsubscribe-Post: List-Unsubscribe=One-Click`` companion is
    present; the mailto: target is the keyless fallback (send an unsubscribe email)."""
    out = {"mailto": [], "https": []}
    for m in re.findall(r"<([^>]+)>", header or ""):
        t = m.strip()
        if t.lower().startswith("mailto:"):
            out["mailto"].append(t[len("mailto:"):])
        elif t.lower().startswith("http"):
            out["https"].append(t)
    return out


def propose(rows, min_count=2):
    """From classified sweep rows, propose noise-killers for recurring archive senders.

    A sender that lands in the archive bucket repeatedly is refilling the inbox — the cure
    is to unsubscribe/filter it at the source, not to archive it again next week. Groups by
    real sending domain, keeps those seen >= min_count, and returns the owned proposals
    sorted by frequency. Marketing-labelled single hits are included too (one is enough to
    justify the unsubscribe)."""
    groups = defaultdict(lambda: {"count": 0, "name": "", "sender": "", "subjects": [],
                                  "labels": set(), "accounts": set()})
    for r in rows:
        if r.get("action") != "archive":
            continue
        sender = r.get("sender", "")
        dom = _domain(sender)
        g = groups[dom]
        g["count"] += 1
        g["name"] = g["name"] or _name(sender)
        g["sender"] = g["sender"] or sender
        subj = r.get("subject", "")
        if subj and subj not in g["subjects"]:
            g["subjects"].append(subj)
        if r.get("label"):
            g["labels"].add(r["label"])
        if r.get("_account"):
            g["accounts"].add(r["_account"])

    proposals = []
    for dom, g in groups.items():
        marketing = any("market" in l.lower() or "newsletter" in l.lower()
                        for l in g["labels"])
        if g["count"] < min_count and not marketing:
            continue
        proposals.append({
            "domain": dom,
            "sender": g["sender"],
            "name": g["name"],
            "count": g["count"],
            "labels": sorted(g["labels"]),
            "accounts": sorted(g["accounts"]),
            "sample_subjects": g["subjects"][:3],
            "action": f"Unsubscribe / create a filter for {dom} so it stops refilling the inbox",
            "status": "proposed",
            "gated_on": _GATED_ON,
        })
    proposals.sort(key=lambda p: p["count"], reverse=True)
    return proposals
