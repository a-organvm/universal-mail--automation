#!/usr/bin/env python3
"""draft_writer.py — the outbound leaf: turn each reply-owed obligation into a ready,
voice-matched DRAFT, addressed to the sender, NEVER sent.

Two effects, both reversible and gated:
  * Always: enrich obligations-ledger.json — each obligation whose protocol owes a reply
    gets a `draft_text` (voice-matched starter) + `draft_to` (the sender's address). This
    is zero-touch: the ready draft just becomes visible in the ledger/face.
  * With --save: persist each draft to Apple Mail's Drafts folder keylessly (Drafts is a
    real folder, so it sticks even on Gmail), IDEMPOTENTLY — a draft is created at most
    once per obligation (tracked in audit/drafts_created.json), so an autonomic beat never
    piles up duplicates.

Draft-only is the entire design: there is no send, no schedule. The user always presses
send; a draft can be deleted any time. Fail-open: a compose/save error skips that one
obligation, never the rest.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.voice import load_voice_profile  # noqa: E402
from core.protocols import _addr  # noqa: E402

_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit", "drafts_created.json")


def _first_name(sender: str) -> str:
    name = (sender or "").split("<")[0].strip().strip('"')
    parts = [p for p in name.split() if p and "@" not in p and not p.isupper()]
    return parts[0] if parts else ""


def _ob_key(ob) -> str:
    """Stable idempotency key for one obligation (so re-runs never re-draft)."""
    mids = ob.get("message_ids") or []
    tail = mids[0] if mids else (ob.get("sample_subjects") or [""])[0][:40]
    return f"{ob.get('cls')}|{ob.get('domain')}|{tail}"


def compose(profile, ob, name: str) -> str:
    """A voice-matched STARTER draft (greeting + class-appropriate body + sign-off).
    Deliberately a starter with explicit [brackets] the user fills — never a fabricated
    commitment, never auto-sent."""
    sender = ob.get("sender", "")
    first = _first_name(sender)
    greeting = profile.greeting.format(first=first).strip() if first else "Hi there,"
    subj = (ob.get("sample_subjects") or [""])[0]
    hint = ob.get("draft_hint") or "Acknowledge receipt and confirm the next step."
    ref = f' regarding "{subj}"' if subj else ""
    body_lines = [
        profile.apply_style(f"Thank you for your message{ref}."),
        "",
        f"[{hint}]",
        "",
        "[Add your specifics here, then send.]",
    ]
    parts = [greeting, "", "\n".join(body_lines), "", profile.sign_off]
    sig = profile.signature or profile.name or name
    if sig:
        parts.append(sig)
    text = "\n".join(parts)
    return text.strip() + "\n"


def _load_state():
    try:
        return set(json.loads(open(_STATE).read()))
    except (OSError, ValueError):
        return set()


def _save_state(keys):
    os.makedirs(os.path.dirname(_STATE), exist_ok=True)
    with open(_STATE, "w") as f:
        json.dump(sorted(keys), f, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Enrich the obligations ledger with ready drafts (never sent).")
    limen_root = os.environ.get("LIMEN_ROOT", os.path.expanduser("~/Workspace/limen"))
    ap.add_argument("--ledger", default=os.environ.get(
        "LIMEN_OBLIGATIONS_LEDGER", os.path.join(limen_root, "obligations-ledger.json")))
    ap.add_argument("--name", default=os.environ.get("LIMEN_MAIL_NAME", "Anthony"))
    ap.add_argument("--save", action="store_true",
                    help="also persist drafts to Apple Mail Drafts (idempotent, never sent)")
    ap.add_argument("--max", type=int, default=int(os.environ.get("LIMEN_MAIL_DRAFTS_MAX", "12")),
                    help="cap how many drafts to persist per run (safety)")
    args = ap.parse_args(argv)

    try:
        ledger = json.loads(open(args.ledger).read())
    except (OSError, ValueError) as e:
        print(f"draft_writer: cannot read ledger {args.ledger}: {e}")
        return 0  # fail-open

    profile = load_voice_profile(name=args.name)
    obligations = ledger.get("obligations", [])
    state = _load_state()
    enriched = saved = skipped = 0

    provider = None
    if args.save:
        try:
            from providers.mailapp import MailAppProvider
            provider = MailAppProvider  # constructed per-account below
        except Exception as e:  # pragma: no cover
            print(f"draft_writer: MailApp unavailable ({e}); enrich-only")
            provider = None

    for ob in obligations:
        if not ob.get("requires_reply"):
            continue
        to_addr = _addr(ob.get("sender", ""))
        # only draft to a real, replyable address (skip relay/role/no-address)
        if "@" not in to_addr or "privaterelay.appleid.com" in to_addr:
            continue
        ob["draft_text"] = compose(profile, ob, args.name)
        ob["draft_to"] = to_addr
        enriched += 1

        if provider is not None and saved < args.max:
            key = _ob_key(ob)
            if key in state:
                ob["draft_saved"] = True
                skipped += 1
                continue
            account = (ob.get("accounts") or [None])[0]
            subj = (ob.get("sample_subjects") or [""])[0]
            re_subj = subj if subj.lower().startswith("re:") else f"Re: {subj}".strip()
            try:
                ok = provider(account=account).create_draft(
                    to_addr, re_subj or "(no subject)", ob["draft_text"], account=account)
            except Exception:
                ok = False
            if ok:
                state.add(key)
                _save_state(state)   # checkpoint AFTER each save → a crash mid-loop can't
                                     # lose the key and re-create a duplicate next beat
                ob["draft_saved"] = True
                saved += 1

    if args.save:
        _save_state(state)

    with open(args.ledger, "w") as f:
        json.dump(ledger, f, indent=2)

    print(f"draft_writer: enriched {enriched} reply drafts"
          + (f"; saved {saved} new to Drafts ({skipped} already present)" if args.save else " (enrich-only)")
          + f" → {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
