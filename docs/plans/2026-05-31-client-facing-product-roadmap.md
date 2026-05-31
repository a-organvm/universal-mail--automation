# universal-mail--automation — Client-Facing Product Roadmap

**Date:** 2026-05-31 | **Status:** planning | **Audience:** product / go-to-market

> This is a public planning document. It deliberately contains **no** credentials, account identifiers,
> internal filesystem paths, or third-party personal data. Operational and security-incident detail is
> tracked privately, out of this repository.

---

## 1. What this is

A multi-provider mail-triage engine that archives and labels low-value mail **while provably never
touching protected senders** (legal, financial, government, platform-account, and user-designated
correspondents). It supports Gmail (REST), generic IMAP, Outlook (Microsoft Graph), and Apple Mail
(AppleScript) behind one interface.

## 2. Positioning — "provable restraint"

The market splits cleanly, and there's a gap in the middle:

- **Consumer inbox tools** (auto-archivers, smart-inbox apps) protect important senders with *soft
  heuristics* a single misclassification can bypass — and keep no defensible record of what they did.
- **Enterprise support/automation bots** keep audit logs, but in a vendor dashboard, and they never
  act on your personal inbox.

Nobody combines a **hard, fail-closed pre-action veto** at the provider chokepoint with an
**independent audit receipt** that re-derives "was this sender protected?" from what *actually*
happened — not from what the engine intended. That combination is the product's moat, and reframed,
the receipt is **compliance evidence** (retention/audit obligations) rather than a safety footnote.

**Beachhead buyer:** solo and small-firm **legal, finance/RIA, and accounting** practices (and the
agencies serving them), for whom one wrongly-archived counsel or regulator email is a malpractice-grade
event. "It usually gets it right" is disqualifying; "it provably never touched X, here's the receipt"
is the whole sale. We deliberately avoid the crowded prosumer AI-inbox lane.

## 3. Current assets (shipped, in this repo)

| Asset | What it gives us |
|---|---|
| **Protected-sender gate** | Fail-closed pre-action veto enforced at multiple depths; decides on the *parsed real domain*; hardened against RFC2047/IDN-punycode/dot-plus/relay tricks and over-match. |
| **`LABEL_IS_MOVE` abstraction** | One gate stays correct across additive-label providers (Gmail/IMAP) and move-on-label providers (Outlook/Mail.app). |
| **Independent audit receipt** | Append-only JSONL recording *actual* post-execution disposition; re-derives protection from the raw sender; raises on any violation; CLI exits non-zero on violation. |
| **Externalized protected config** | Curated, gitignored local list (legal/gov/financial/platform/orgs/self categories) merged with synthetic examples. |
| **Test coverage** | 189 passing / 3 skipped; provider-parity probes for the move-vs-label invariant. |

## 4. MVP gaps (what blocks a paying customer), ranked by how hard they block

1. **Multi-tenant auth** — the real wall: two of the four providers require the *customer* to
   self-register an OAuth app. Needs a guided onboarding flow.
2. **Provider verification/compliance** (e.g. Google's restricted-scope review) — affordable **only
   because** the engine never permanently deletes (moves-only). The safety design is also the cost moat;
   adding hard-delete would multiply the verification cost. Treat moves-only as a load-bearing decision.
3. **Undo / restore** — table-stakes trust feature: replay the inverse disposition from the audit log.
4. **Scheduler reliability** — the unattended runner needs portable paths and a clean install path.
5. **Client surface** — no UI/CLI packaging a non-engineer can run.
6. **Trust/compliance docs** — the strongest technical asset isn't yet a buyer-facing story.

## 5. The "superpowered" layer — Compliance Evidence Pack

Promote the audit receipt from an internal safeguard to the **headline deliverable**: an exportable,
tamper-evident **Compliance Evidence Pack** — per-run proof of which senders were protected, what was
moved, and what was provably never touched, in a form a compliance officer or auditor can keep. This is
the feature competitors structurally can't copy without rebuilding around a hard gate + independent
observer.

## 6. Four-phase roadmap

- **Phase 0 — Harden.** Credential-hygiene pass (broker-only secrets, no hardcoded defaults); ship
  undo/restore; fix the scheduler (portable runner + clean install); quarantine any pre-gate legacy
  scripts; promote the move-vs-label probes into the test suite.
- **Phase 1 — MVP.** Multi-tenant onboarding/auth; provider verification; minimal client surface.
- **Phase 2 — Superpowered.** Compliance Evidence Pack as the headline; trust-center page.
- **Phase 3 — GA.** Packaging, billing, docs, support path.

## 7. Business model (working hypothesis)

| Tier | Who | Price (hypothesis) |
|---|---|---|
| Free | individuals, one account | $0 |
| Pro | power users, multi-account | ~$40–50 / mo |
| Team | small firms | ~$80–120 / mo |
| Enterprise / Compliance | regulated practices needing the Evidence Pack | custom |
| Pass | one-time cleanup engagement | ~$19 |

## 8. Top next actions

1. **Phase 0 security hardening** — credential hygiene + secrets-broker enforcement (internal, prerequisite to any external launch).
2. **Fix the scheduler** — portable runner + clean install path.
3. **Ship undo/restore** — inverse-replay from the audit log; the #1 table-stakes trust gap.
4. **Trust-center page** — convert the gate + receipt into the buyer-facing compliance story.
5. **Quarantine pre-gate legacy scripts + promote provider-parity probes into the test suite** — protect the keystone invariant.

## 9. Open product questions

- Final beachhead confirmation (legal/finance/compliance) and the "provable restraint" messaging.
- Build order across Phase 0 → Phase 1 once auth scope is sized.

---

*Companion: `docs/plans/2026-05-31-provenance-evolution.md` (engineering graduation plan). Operational/security continuity is tracked privately, outside this repository.*
