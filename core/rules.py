"""
Shared email categorization rules.

Defines the LABEL_RULES taxonomy, priority labels, priority tiers (Eisenhower matrix),
and categorization functions used across all email providers.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr
from typing import Dict, List, Any, Optional, Tuple


# ============================================================================
# PRIORITY TIER SYSTEM (Eisenhower Matrix)
# ============================================================================

@dataclass(frozen=True)
class PriorityTier:
    """Configuration for a priority tier."""
    number: int
    name: str
    color: str
    folder: Optional[str]
    keep_in_inbox: bool
    star: bool


PRIORITY_TIERS: Dict[int, PriorityTier] = {
    1: PriorityTier(
        number=1,
        name="Critical",
        color="red",
        folder="Action/Critical",
        keep_in_inbox=True,
        star=True,
    ),
    2: PriorityTier(
        number=2,
        name="Important",
        color="yellow",
        folder="Action/Important",
        keep_in_inbox=True,
        star=False,
    ),
    3: PriorityTier(
        number=3,
        name="Delegate",
        color="blue",
        folder="Action/Delegate",
        keep_in_inbox=False,
        star=False,
    ),
    4: PriorityTier(
        number=4,
        name="Reference",
        color="green",
        folder=None,  # Just categorize, archive
        keep_in_inbox=False,
        star=False,
    ),
}

# ============================================================================
# LABEL TAXONOMY - Comprehensive categorization rules
# ============================================================================

LABEL_RULES: Dict[str, Dict[str, Any]] = {
    # Development & Code
    "Dev/GitHub": {
        "patterns": [
            r"github\.com",
            r"notifications@github",
            r"@reply\.github\.com",
            r"copilot",
            r"ivi374forivi",
        ],
        "priority": 1,
        "tier": 2,  # Important - code reviews may need attention
        "time_sensitive": False,
    },
    "Dev/Code-Review": {
        "patterns": [r"coderabb", r"sourcery", r"qodo", r"codacy", r"copilot", r"llamapre"],
        "priority": 2,
        "tier": 2,  # Important - reviews need response
        "time_sensitive": True,
    },
    "Dev/Infrastructure": {
        "patterns": [
            r"cloudflare",
            r"vercel",
            r"netlify",
            r"digitalocean",
            r"railway",
            r"render\.com",
            r"newrelic",
            r"pieces\.app",
            r"hashicorp",
        ],
        "priority": 3,
        "tier": 3,  # Delegate/Monitor - alerts can be checked later
        "time_sensitive": False,
    },
    "Dev/GameDev": {
        "patterns": [r"unity3d\.com", r"unity\.com", r"unrealengine", r"godotengine"],
        "priority": 3,
        "tier": 3,
        "time_sensitive": False,
    },
    # AI Services
    "AI/Services": {
        "patterns": [
            r"openai",
            r"anthropic",
            r"claude",
            r"x\.ai",
            r"xai\.com",
            r"xAI LLC",
            r"perplexity",
            r"(^|@|\.)meta\.com\b",  # anchored to the From host (not 'metabolism' etc.)
            r"ollama",
            r"sudowrite",
        ],
        "priority": 12,  # de-ranked below Tech/Security (9) so login alerts win; meta.com also PROTECTED
        "tier": 3,  # Delegate - informational
        "time_sensitive": False,
    },
    "AI/Grok": {
        "patterns": [r"grok", r"x\.ai.*grok"],
        "priority": 5,
        "tier": 3,
        "time_sensitive": False,
    },
    "AI/Data Exports": {
        "patterns": [r"data export", r"export is ready", r"download.*data"],
        "priority": 6,
        "tier": 2,  # Important - exports may expire
        "time_sensitive": True,
    },
    # Finance & Payments
    "Finance/Banking": {
        "patterns": [
            r"chase",
            r"capital.?one",
            r"verizon",
            r"(^|@|\.)gemini\.com\b",  # crypto exchange, not Google's Gemini AI
            r"experian",
            r"chime",
            r"kikoff",
            r"self\.inc",
            r"nav\.com",
            r"bankofamerica",
            r"wellsfargo",
            r"(^|@|\.)citi(bank|cards|group)?\.com\b",  # not 'publicity'/'felicity'
            r"usbank",
            r"(^|@|\.)ally\.com\b",       # not 'really'/'Allyson'
            r"(^|@|\.)marcus\.com\b",     # not arbitrary 'marcus'
            r"(^|@|\.)regions\.com\b",    # not 'regions of Italy'
            r"(^|@|\.)pnc\.com\b",
        ],
        "priority": 7,
        "tier": 1,  # Critical - financial alerts
        "time_sensitive": True,
    },
    "Finance/Payments": {
        "patterns": [
            r"paypal",
            r"stripe",
            r"kovo",
            r"cash.?app",
            r"true.?finance",
            r"square",
            r"braintree",
            r"plaid",
            r"capitalone",
            r"joingerald",
            r"vola",
            r"venmo",
            r"zelle",
            r"(^|@|\.)att\.(com|net)\b",  # AT&T domains, not 'seattle'/'attachment'/'attorney'
            r"xfinity",
            r"spectrum",
            r"conedison",
            r"discover",
            r"american.?express",
            r"barclaycard",
            r"statement",
            r"invoice",
            r"payment.*due",
        ],
        "priority": 8,
        "tier": 2,  # Important - bills and payments
        "time_sensitive": True,
    },
    "Finance/Tax": {
        "patterns": [
            r"intuit",
            r"turbotax",
            r"hrblock",
            r"taxact",
            r"taxslayer",
            # irs.gov deliberately NOT here: mail from the IRS itself is
            # Personal/Government (tier 1 Critical), not tax-software vendor
            # mail (review U065). Vendor patterns only.
            r"taxrise",
        ],
        "priority": 8,
        "tier": 2,  # Important - tax deadlines
        "time_sensitive": True,
    },
    # Subscriptions & Services
    "Tech/Security": {
        "patterns": [
            r"1password",
            r"security.*alert",
            r"login.*detected",
            r"new.*device",
            r"password.*reset",
            r"verification.*code",
            r"dropbox",
            r"todoist",
            r"login\.gov",
        ],
        "priority": 9,
        "tier": 1,  # Critical - security alerts
        "time_sensitive": True,
    },
    "Tech/Google": {
        "patterns": [
            r"@google\.com",
            r"cloudsupport@",
            r"google.*cloud",
            r"gcp",
            r"workspace",
            r"payments\.google\.com",
        ],
        "priority": 9,
        "tier": 2,  # Important - support cases
        "time_sensitive": True,
    },
    # Commerce & Shopping
    "Shopping": {
        "patterns": [
            r"uber",
            r"amazon",
            r"ebay",
            r"etsy",
            r"walmart",
            r"target",
            r"deepview",
            r"squarespace",
            r"lafitness",
            r"bestbuy",
            r"costco",
            r"wayfair",
            r"chewy",
            r"zara",
            r"(^|@|\.)hm\.com\b",   # not 'firmhm.com'
            r"(^|@|\.)gap\.com\b",  # not 'mind-the-gap.com'
            r"oldnavy",
            r"nike",
            r"adidas",
            r"nordstrom",
            r"macys",
            r"uniqlo",
            r"lululemon",
            r"order.*confirm",
            r"(order|package|item|your shipment)[\s\S]{0,20}shipp(ed|ing)",  # not 'prescription has shipped'
            r"\btracking (number|no\.?|#|id)\b",  # shipment tracking id, not the verb 'tracking'
            r"fjallraven",
        ],
        "priority": 10,
        "tier": 4,  # Reference - order confirmations
        "time_sensitive": False,
    },
    # Health & Pharmacy
    "Personal/Health": {
        "patterns": [
            r"walgreens",
            r"cvs",
            r"pharmacy",
            r"prescription",
            r"health\.nyc\.gov",
            r"trinity-health",
            r"myhealth",
        ],
        "priority": 9,  # wins ties over Shopping (10) so health mail is never archived as commerce
        "tier": 2,  # Important - health matters
        "time_sensitive": True,
    },
    # Social Networks
    "Social/LinkedIn": {
        "patterns": [
            r"linkedin\.com",
            r"linkedin.*network",
            r"linkedin.*job",
        ],
        "priority": 11,
        "tier": 3,  # Delegate - social can wait
        "time_sensitive": False,
    },
    # Travel
    "Travel": {
        "patterns": [
            r"united\.com",
            r"(^|@|\.)aa\.com\b",  # American Airlines, not 'panamaa.com'
            r"delta\.com",
            r"southwest",
            r"jetblue",
            r"alaskaair",
            r"spirit",
            r"flyfrontier",
            r"marriott",
            r"hilton",
            r"hyatt",
            r"ihg",
            r"airbnb",
            r"vrbo",
            r"booking\.com",
            r"hotels\.com",
            r"expedia",
            r"kayak",
            r"priceline",
            r"orbitz",
            r"hotwire",
            r"itinerary",
            r"boarding.*pass",
            r"flight.*confirm",
        ],
        "priority": 11,
        "tier": 2,  # Important - travel may need action
        "time_sensitive": True,
    },
    # Entertainment & Media
    "Entertainment": {
        "patterns": [
            r"fandango",
            r"audible",
            r"netflix",
            r"spotify",
            r"letterboxd",
            r"popcorn.?frights",
            r"warprecords",
            r"musescore",
            r"justwatch",
            r"thefilmjunkies",
            r"louisck",
        ],
        "priority": 12,
        "tier": 4,  # Reference
        "time_sensitive": False,
    },
    # Education
    "Education/Research": {
        "patterns": [
            r"coursera",
            r"udemy",
            r"skillshare",
            r"edx",
            r"khanacademy",
            r"scholar\.google",
            r"researchgate",
            r"arxiv",
            r"academia\.edu",
            r"orcid\.org",
        ],
        "priority": 13,
        "tier": 3,  # Delegate - can be reviewed later
        "time_sensitive": False,
    },
    # Professional Services
    "Professional/Jobs": {
        "patterns": [
            r"higheredjobs",
            r"indeed",
            r"linkedin.*jobs",
            r"glassdoor",
            r"jobot",
            r"builtin\.com",
            r"ziprecruiter",
            r"monster",
            r"recruiterflow",
        ],
        "priority": 14,
        "tier": 2,  # Important - job opportunities
        "time_sensitive": True,
    },
    "Professional/Legal": {
        # Generic legal cues only. A specific firm's mail is identified for
        # PROTECTION via the gitignored local config, not hardcoded here (PII).
        "patterns": [
            r"legalzoom",
            r"law\.com",
            r"attorney",
            r"legal.*notice",
        ],
        "priority": 14,
        "tier": 2,  # Important - legal matters
        "time_sensitive": True,
    },
    # Domain Services
    "Services/Domain": {
        "patterns": [
            r"namecheap", r"godaddy", r"domain.*renew",
            r"\b(dns (record|zone|settings)|nameserver)\b",  # not any literal 'dns' run
            r"e\.godaddy\.com",
        ],
        "priority": 15,
        "tier": 2,  # Important - domain renewals critical
        "time_sensitive": True,
    },
    # Notifications (catch-all for services)
    "Notification": {
        "patterns": [
            r"notification",
            r"alert",
            r"reminder",
            r"automatic.?appointment",
            r"udemy.*instructor",
            r"google.*workspace",
            r"trinity-health",
            r"deepview",
            r"todoist",
        ],
        "priority": 16,
        "tier": 3,  # Delegate - informational
        "time_sensitive": False,
    },
    # Marketing
    "Marketing": {
        "patterns": [
            r"unsubscribe",
            r"newsletter",
            r"\bpromo(tion|tional)?\b",
            r"special.*offer",
            r"(% ?off|limited[- ]time|exclusive offer|flash sale|use code|coupon)",
            r"discount",
            r"(flash sale|\d+% ?off|clearance sale)",
            r"hims",
            r"substack",
            r"scaleclients",
            r"collabwriting",
            r"beehiiv",
            r"coursera",
            r"jupitrr",
            r"myhumandesign",
            r"ibo\.org",
            r"sendfox",
        ],
        "priority": 17,
        "tier": 4,  # Reference - archive
        "time_sensitive": False,
    },
    # Cloud Storage & Files
    "Tech/Storage": {
        "patterns": [
            r"filerev",
            r"(^|@|\.)box\.com\b",   # not 'toolbox.com'
            r"onedrive",
            r"gdrive",
            r"(^|@|\.)icloud\.com\b",  # the iCloud product domain, NOT every Hide-My-Email relay
            r"sync\.com",
        ],
        "priority": 17,
        "tier": 3,  # Delegate
        "time_sensitive": False,
    },
    # Government & Official
    "Personal/Government": {
        "patterns": [
            r"\.gov$",
            r"@.*\.gov",
            r"flhsmv",
            r"passport",
            r"social.*security",
            r"ssa\.gov",
            r"irs\.gov",
            r"dmv",
            r"state\.fl\.us",
        ],
        # Government mail is tier-1 Critical, so its priority must OUTRANK
        # every overlapping lower-tier rule. At the old 17 it lost to
        # Finance/Tax (8: irs.gov demoted to tier 2) and tied with Marketing
        # (17: an ssa.gov newsletter demoted to tier 4 by dict order alone) —
        # reviews U064/U065. 4 sits below the Dev rules (no .gov overlap)
        # and above everything a government sender can also match.
        "priority": 4,
        "tier": 1,  # Critical - government matters
        "time_sensitive": True,
    },
    # Personal — self mail is identified/protected by the gate (_self_match +
    # SELF_LOCALPARTS, loaded from the gitignored local config), so no self
    # address is hardcoded here. These are generic relationship keywords only.
    "Personal": {
        "patterns": [r"family", r"mom", r"dad"],
        "priority": 18,
        "tier": 1,  # Critical - personal emails
        "time_sensitive": True,
    },
    # Awaiting Action
    "Awaiting Reply": {
        "patterns": [r"awaiting.*reply", r"pending.*response"],
        "priority": 19,
        "tier": 2,  # Important - needs follow-up
        "time_sensitive": True,
    },
    # Default catch-all
    "Misc/Other": {
        "patterns": [r".*"],
        "priority": 999,
        "tier": 4,  # Reference - uncategorized
        "time_sensitive": False,
    },
}

# Labels that should trigger starring (high priority)
PRIORITY_LABELS = {
    "Finance/Banking",
    "Tech/Security",
}

# Labels that should remain in inbox (not archived)
KEEP_IN_INBOX = {
    "Finance/Banking",
    "Tech/Security",
    "Personal",
    "Awaiting Reply",
}


# ============================================================================
# PROTECTED SENDERS — HARD, FAIL-CLOSED NEVER-ARCHIVE GATE
# ============================================================================
# The product's headline safety guarantee. This gate is SENDER-based (not
# label-based), so it does NOT depend on correct categorization: a protected
# sender is shielded even if a noise rule would otherwise match it.
#
# Enforcement contract — every triage path MUST obey this before any archive/move:
#   1. For each candidate message, call is_protected_sender(from_header).
#   2. If True, DROP it from the action set (never remove INBOX, never move out
#      of inbox). Enforce at the choke point, NOT merely as a query-time filter.
#   3. FAIL CLOSED: an empty/unparseable sender is treated as protected.
#
# MATCHING SEMANTICS (hardened 2026-05-31 — see normalize_sender):
# Protection is decided on the PARSED, decoded REAL domain of the addr-spec, with
# subdomain-boundary semantics (domain == entry OR domain endswith '.'+entry) —
# NOT a raw substring of the From header. This closes the fail-OPEN class where a
# byte-level transform of the dots hid a genuinely protected sender:
#   • iCloud Hide My Email / privaterelay rewrites ("example-lawfirm_com_TOKEN@icloud.com")
#   • RFC 2047 encoded-words ("=?utf-8?B?...?=")
#   • IDN / punycode ("xn--...")
#   • Gmail dot/plus canonicalization of the self mailbox
# and the fail-CLOSED-WRONG class where containment over-matched
# ("purchase.com" ⊃ "chase.com"; display-name spoofs; subdomain left-label spoofs).
# A specific subdomain (alerts.example-bank.com) still protects only that stream
# and not a sibling marketing stream (example-bank-marketing.com). Any US *.gov sender
# (terminal label, on the recovered domain) is auto-protected.

# PRIVACY: this is a PUBLIC repo. A user's real protected list (their lawyer,
# banks, government accounts, employers, self) is a sensitive relationship/finance
# map and MUST NOT be committed. So the code ships only GENERIC, non-PII defaults
# (universal platform/security/gov/e-sign services any user would want) plus clearly
# SYNTHETIC examples; each user supplies their own specifics via a gitignored local
# config (PROTECTED_SENDERS_FILE or ./config/protected_senders.local.txt), which is
# MERGED in at import. The gate LOGIC is identical regardless of the data source.
EXAMPLE_PROTECTED_SENDERS: List[str] = [
    # --- Generic, non-PII services (safe, sensible defaults for everyone) ---
    "docusign.net",                                  # e-signature (legal docs)
    "irs.gov", "ssa.gov", "studentaid.gov", "login.gov",  # US government
    "apple.com", "appleid.com",  # appleid.com covers privaterelay.appleid.com + e.appleid.com
    "google.com", "accounts.google.com", "anthropic.com",
    "1password.com", "meta.com", "facebookmail.com",  # account-takeover alert backstops
    "chase.com",                                      # demo financial-alert backstop
    # --- SYNTHETIC placeholders (replace with your real entries in the local file) ---
    "example-lawfirm.com",                           # your attorney's domain
    "example-bank.com", "alerts.example-bank.com",   # your bank (account/alerts only)
    "example-nonprofit.org",                         # an org you have a relationship with
    # NOTE: 'example-bank-marketing.com' is intentionally NOT here — it documents
    # that a sibling MARKETING domain is not protected just because the bank is.
]

# iCloud relay carriers whose local-part encodes the real sender's address.
RELAY_DOMAINS = {"icloud.com", "privaterelay.appleid.com"}
# Gmail mailboxes that canonicalize away dots and +tags in the local part.
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
# Synthetic self placeholder; the real self mailbox(es) load from the local config.
EXAMPLE_SELF_LOCALPARTS = {"youremail"}


def _load_local_protected() -> Tuple[List[str], set]:
    """Load the user's REAL protected domains + self mailboxes from a gitignored
    local config so PII never enters this PUBLIC repo.

    Format: one entry per line; blank lines and '#' comments ignored; a line
    'self: <localpart-or-address>' registers a self mailbox (dots stripped, Gmail
    canonical). Path: $PROTECTED_SENDERS_FILE, else ./config/protected_senders.local.txt.
    Absent file -> empty (the example defaults still apply). Never raises.
    """
    import os
    path = os.environ.get("PROTECTED_SENDERS_FILE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "protected_senders.local.txt",
    )
    domains: List[str] = []
    selfs: set = set()
    try:
        # errors="replace": a non-UTF-8 byte must NOT raise UnicodeDecodeError and
        # crash the import (disabling the whole gate). Bad bytes degrade to U+FFFD
        # in that one line (which then matches nothing); every clean line still loads.
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if line.lower().startswith("self:"):
                    lp = line.split(":", 1)[1].strip().lower().split("@")[0].replace(".", "")
                    if lp:
                        selfs.add(lp)
                else:
                    domains.append(line.lower())
    except (FileNotFoundError, OSError):
        pass
    except Exception:
        # Belt-and-suspenders: a malformed local config must NEVER crash the gate's
        # import (honors this function's documented "Never raises" contract). Fall
        # back to whatever parsed cleanly plus the shipped example defaults.
        pass
    return domains, selfs


_local_domains, _local_selfs = _load_local_protected()
# Real entries (from the gitignored local file) are MERGED with the shipped
# examples; the example domains never receive real mail, so the merge is harmless.
PROTECTED_SENDERS: List[str] = list(dict.fromkeys(EXAMPLE_PROTECTED_SENDERS + _local_domains))
# Self mailbox(es), dot/plus-canonicalized (dots stripped, lowercased).
SELF_LOCALPARTS = EXAMPLE_SELF_LOCALPARTS | _local_selfs


def _decode_mime(raw: str) -> str:
    """RFC 2047-decode encoded-words ('=?utf-8?B?...?=') to plain text.

    Done BEFORE parsing so an encoded From can never hide the real address from
    the gate. Never raises — falls back to the raw header on any decode error.
    """
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _idna_decode(domain: str) -> str:
    """Punycode (xn--) -> Unicode per label, so an IDN/homoglyph domain is
    compared on its U-label, not its opaque A-label. Per-label and crash-safe:
    an undecodable label is left as-is rather than failing the whole gate."""
    out = []
    for lbl in domain.split("."):
        if lbl.startswith("xn--"):
            try:
                out.append(lbl.encode("ascii").decode("idna"))
            except Exception:
                out.append(lbl)  # leave A-label on failure; never crash the gate
        else:
            out.append(lbl)
    return ".".join(out)


def _gov_protected(domain: str) -> bool:
    """US .gov only, anchored to the TERMINAL label of the recovered domain.
    'irs.gov' -> True; 'irs.gov.attacker.com' -> False; 'service.gov.uk' -> False.
    A '.gov' in a local part can never reach here (we only ever pass the domain)."""
    return bool(domain) and domain.split(".")[-1] == "gov"


def _domain_matches(domain: str, entry: str) -> bool:
    """Boundary match: equality OR proper subdomain. Kills substring embeds
    ('purchase.com' != 'chase.com') and left-label spoofs
    ('example-lawfirm.com.attacker.example' does not end with '.example-lawfirm.com')."""
    return domain == entry or domain.endswith("." + entry)


def _is_protected_domain(domain: str) -> bool:
    """True if the recovered real domain is government or matches a protected
    entry on a domain/subdomain boundary."""
    if not domain:
        return False
    if _gov_protected(domain):
        return True
    return any(_domain_matches(domain, e) for e in PROTECTED_SENDERS)


def _relay_domain_candidates(local: str) -> set:
    """Recover candidate real domains from an iCloud relay local-part.

    iCloud Hide My Email / forwarding rewrites the real sender into the local
    part with dots-as-underscores, e.g. 'user_at_example-lawfirm_com_TOKEN' or
    'example-lawfirm_com_TOKEN'. The trailing random token may itself be MULTI-segment
    ('..._tok_tok'), so we generate a candidate for EVERY progressive truncation
    of trailing underscore-segments (not just one). Over-recovery only ever
    protects MORE — the safe direction for a fail-closed gate."""
    s = local.lower()
    base = s.partition("_at_")[2] if "_at_" in s else s
    parts = base.split("_")
    # full form + each prefix formed by dropping 1..N trailing segments
    variants = {"_".join(parts[:k]) for k in range(1, len(parts) + 1)}
    cands = set()
    for v in variants:
        dom = v.replace("_", ".").strip(".")
        if "." in dom:
            cands.add(dom)
    return cands


def _best_relay_domain(cands: set) -> str:
    """Pick the most-likely REAL domain from relay candidates for categorization.
    Prefer a candidate whose terminal label looks like a TLD (all-alpha) and the
    fewest labels (the token-appended variant carries a junk last label)."""
    real = [c for c in cands
            if c.split(".")[-1].isalpha() and 2 <= len(c.split(".")[-1]) <= 18]
    return min(real, key=lambda c: c.count(".")) if real else ""


def _resolve_addr(addr: Optional[str]) -> Tuple[str, str]:
    """Resolve a SINGLE addr-spec to (email, real_domain).

    rpartition on the LAST '@' (so a quoted local part carrying a protected token
    can't win), strip/lower/trailing-dot, IDNA-decode, then iCloud-relay-decode.
    Returns ('', '') when there is no parseable domain (caller fails closed).
    """
    addr = (addr or "").strip().strip("<>")
    if "@" not in addr:
        return ("", "")
    local, _, domain = addr.rpartition("@")
    domain = domain.strip().strip("<>").rstrip(".").lower()
    domain = _idna_decode(domain)
    if domain in RELAY_DOMAINS or domain.endswith(".appleid.com"):
        cands = _relay_domain_candidates(local)
        # Protection first: if ANY recovered candidate is protected, surface it.
        for cand in cands:
            if _is_protected_domain(cand):
                if "_at_" in local.lower():
                    user = local.lower().partition("_at_")[0]
                    return (f"{user}@{cand}", cand)
                return ("", cand)
        # Not protected, but still prefer the recovered REAL domain over the
        # carrier so relay mail is categorized by its true sender (an unknown
        # sender then falls to Misc/Other and is KEPT, not archived as storage).
        real = _best_relay_domain(cands)
        if real:
            return ("", real)
        # Undecodable relay local-part (Apple's own 'noreply'/'id'): keep the
        # carrier/appleid domain so appleid.com still matches the gate.
    return (addr, domain)


def normalize_sender(raw_from: Optional[str]) -> Tuple[str, str, str]:
    """Parse a raw From header into (display, email, domain) for the FIRST/primary
    address (used by categorization). The protection gate uses every address —
    see is_protected_sender / _iter_sender_domains.

    - RFC 2047-decodes encoded-words BEFORE parsing.
    - RFC 5322-parses via parseaddr (the display NAME never feeds the gate).
    - Detects iCloud/privaterelay/appleid relay local-parts and recovers the
      embedded REAL domain; IDNA/punycode-decodes the domain.
    Returns ('', '', '') for empty input and ('<display>', '', '') for an
    unparseable address, so the caller fails closed on an empty domain.
    """
    if not raw_from or not raw_from.strip():
        return ("", "", "")
    decoded = _decode_mime(raw_from)
    display, addr = parseaddr(decoded)
    if "@" not in addr:
        cand = decoded.strip().strip("<>")
        addr = cand if "@" in cand else ""
    email_, domain = _resolve_addr(addr)
    if not domain:
        return (display, "", "")
    return (display, email_, domain)


def _iter_sender_domains(raw_from: str):
    """Yield (email, domain) for EVERY address in a (possibly multi-address) From,
    each relay/MIME/IDNA-decoded. The gate matches the UNION so a protected sender
    listed alongside others (e.g. 'Lawyer <a@firm>, Assistant <b@bulk>') can't
    escape via the last-'@' rule. Addresses with no resolvable domain are skipped."""
    decoded = _decode_mime(raw_from)
    for _disp, addr in getaddresses([decoded]):
        email_, domain = _resolve_addr(addr)
        if domain:
            yield (email_, domain)


def _self_match(addr: str, domain: str) -> bool:
    """Gmail dot/plus canonicalization for the self mailbox: e.g. 'your.email',
    'youremail', 'y.o.u.r.e.m.a.i.l', and 'youremail+tag' are one mailbox.
    Real self localparts are loaded into SELF_LOCALPARTS from the local config."""
    if domain not in GMAIL_DOMAINS:
        return False
    local = addr.rpartition("@")[0].lower().split("+", 1)[0].replace(".", "")
    return local in SELF_LOCALPARTS


def is_protected_sender(sender: Optional[str]) -> bool:
    """Hard gate: True if this sender must NEVER be archived / moved out of inbox.

    FAIL CLOSED: empty/None/unparseable sender returns True (protect on
    uncertainty). Matches the UNION over EVERY address in the From (so a protected
    sender listed first or second in a multi-address header can't escape), each on
    its parsed, relay/MIME/IDNA-decoded REAL domain with subdomain-boundary
    semantics, plus a US-.gov terminal-label rule and a Gmail-canonicalized self
    match. The raw header's display name NEVER participates in the decision.
    """
    if not sender or not sender.strip():
        return True  # fail closed: never archive what we can't identify
    saw_domain = False
    for addr, domain in _iter_sender_domains(sender):
        saw_domain = True
        if _gov_protected(domain) or _self_match(addr, domain) or _is_protected_domain(domain):
            return True
    # No resolvable address at all -> fail closed; otherwise no address matched.
    return not saw_domain


def is_archivable(sender: Optional[str]) -> bool:
    """Convenience inverse of is_protected_sender() for filtering action sets."""
    return not is_protected_sender(sender)


def partition_protected(senders_by_id: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """Split {message_id: from_header} into (archivable_ids, protected_ids).

    The protected count is the trust receipt every run should report.
    """
    archivable: List[str] = []
    protected: List[str] = []
    for msg_id, sender in senders_by_id.items():
        (protected if is_protected_sender(sender) else archivable).append(msg_id)
    return archivable, protected


# ============================================================================
# VIP SENDER SYSTEM
# ============================================================================

@dataclass
class VIPSender:
    """Configuration for a VIP sender."""
    pattern: str
    tier: int
    star: bool
    label_override: Optional[str] = None  # Override the matched label
    note: str = ""  # Human-readable note


# VIP senders always get priority treatment regardless of category
# Patterns are matched against the sender (From header)
VIP_SENDERS: Dict[str, VIPSender] = {
    # Example VIP patterns (customize for your use case)
    # "ceo@company.com": VIPSender(
    #     pattern=r"ceo@company\.com",
    #     tier=1,
    #     star=True,
    #     note="CEO",
    # ),
    # ".*@important-client.com": VIPSender(
    #     pattern=r".*@important-client\.com",
    #     tier=1,
    #     star=True,
    #     note="Important client domain",
    # ),
}


# ============================================================================
# CATEGORIZATION FUNCTIONS
# ============================================================================

@dataclass
class CategorizationResult:
    """Result of categorizing an email."""
    label: str
    tier: int
    time_sensitive: bool
    tier_config: PriorityTier
    is_vip: bool = False
    vip_note: str = ""


def check_vip_sender(sender: str) -> Optional[Tuple[VIPSender, str]]:
    """
    Check if a sender matches a VIP pattern.

    Args:
        sender: The From header value

    Returns:
        Tuple of (VIPSender, matched_key) if VIP, None otherwise
    """
    sender_lower = sender.lower()
    for key, vip in VIP_SENDERS.items():
        if re.search(vip.pattern, sender_lower, re.IGNORECASE):
            return (vip, key)
    return None


def is_vip_sender(sender: str) -> bool:
    """Check if a sender is a VIP."""
    return check_vip_sender(sender) is not None


def get_vip_senders() -> Dict[str, VIPSender]:
    """Get the current VIP senders dict."""
    return VIP_SENDERS.copy()


def add_vip_sender(
    key: str,
    pattern: str,
    tier: int = 1,
    star: bool = True,
    label_override: Optional[str] = None,
    note: str = "",
) -> None:
    """
    Add a VIP sender at runtime.

    Args:
        key: Unique key for this VIP (usually the pattern or email)
        pattern: Regex pattern to match sender
        tier: Priority tier (1=Critical, 2=Important)
        star: Whether to star messages from this sender
        label_override: Optional label to use instead of categorization
        note: Human-readable note about this VIP
    """
    VIP_SENDERS[key] = VIPSender(
        pattern=pattern,
        tier=tier,
        star=star,
        label_override=label_override,
        note=note,
    )


def categorize_message(headers: List[Dict[str, str]]) -> str:
    """
    Categorize an email based on headers.

    Args:
        headers: List of header dicts with 'name' and 'value' keys

    Returns:
        Label name from LABEL_RULES
    """
    sender = ""
    subject = ""
    for header in headers:
        name = header.get("name", "").lower()
        if name == "from":
            sender = header.get("value", "")
        elif name == "subject":
            subject = header.get("value", "")

    return categorize_from_strings(sender, subject)


def categorize_from_strings(sender: str, subject: str) -> str:
    """
    Categorize an email based on sender and subject strings.

    Args:
        sender: The From header value
        subject: The Subject header value

    Returns:
        Label name from LABEL_RULES
    """
    result = categorize_with_tier(sender, subject)
    return result.label


def categorize_with_tier(sender: str, subject: str) -> CategorizationResult:
    """
    Categorize an email and return full tier information.

    VIP senders are checked first and override normal categorization rules.

    Args:
        sender: The From header value
        subject: The Subject header value

    Returns:
        CategorizationResult with label, tier, time_sensitive, and VIP info
    """
    # Check VIP senders first - they get priority treatment
    vip_match = check_vip_sender(sender)
    if vip_match:
        vip, vip_key = vip_match
        tier = vip.tier
        tier_config = PRIORITY_TIERS.get(tier, PRIORITY_TIERS[1])

        # Use label override if specified, otherwise do normal categorization
        if vip.label_override:
            label = vip.label_override
            rule = LABEL_RULES.get(label, {"time_sensitive": True})
            time_sensitive = rule.get("time_sensitive", True)
        else:
            # Still categorize normally but use VIP tier
            combined_text = f"{sender} {subject}".lower()
            label = _find_best_label(combined_text)
            rule = LABEL_RULES.get(label, {})
            time_sensitive = rule.get("time_sensitive", True)  # VIP is time-sensitive

        return CategorizationResult(
            label=label,
            tier=tier,
            time_sensitive=time_sensitive,
            tier_config=tier_config,
            is_vip=True,
            vip_note=vip.note,
        )

    # Normal categorization
    combined_text = f"{sender} {subject}".lower()
    label = _find_best_label(combined_text)

    rule = LABEL_RULES[label]
    tier = rule.get("tier", 4)
    time_sensitive = rule.get("time_sensitive", False)
    tier_config = PRIORITY_TIERS.get(tier, PRIORITY_TIERS[4])

    return CategorizationResult(
        label=label,
        tier=tier,
        time_sensitive=time_sensitive,
        tier_config=tier_config,
        is_vip=False,
        vip_note="",
    )


def _find_best_label(combined_text: str) -> str:
    """Find the best matching label for combined sender+subject text.

    Equal-priority matches tie-break on TIER (1=Critical first), never on
    dict-insertion order: with strict priority-only comparison a tier-1 rule
    sharing its priority with an earlier-inserted tier-4 rule silently lost —
    e.g. an ssa.gov notice containing the word "newsletter" was filed as
    Marketing/Reference instead of Government/Critical (review U064)."""
    best_match = None
    best_key = (9999, 9)  # (priority, tier): lower wins on both axes

    for label_name, rule_config in LABEL_RULES.items():
        for pattern in rule_config["patterns"]:
            if re.search(pattern, combined_text, re.IGNORECASE):
                key = (rule_config["priority"], rule_config.get("tier", 4))
                if key < best_key:
                    best_match = label_name
                    best_key = key
                break

    return best_match or "Misc/Other"


def get_tier_for_label(label: str) -> int:
    """Get the priority tier for a label."""
    rule = LABEL_RULES.get(label, {})
    return rule.get("tier", 4)


def get_tier_config(tier: int) -> PriorityTier:
    """Get the configuration for a priority tier."""
    return PRIORITY_TIERS.get(tier, PRIORITY_TIERS[4])


def should_star(label: str) -> bool:
    """Check if a label should trigger starring."""
    # Check both legacy PRIORITY_LABELS and new tier-based starring
    if label in PRIORITY_LABELS:
        return True
    tier = get_tier_for_label(label)
    tier_config = get_tier_config(tier)
    return tier_config.star


def should_keep_in_inbox(label: str) -> bool:
    """Check if a label should remain in inbox."""
    # Check both legacy KEEP_IN_INBOX and new tier-based inbox retention
    if label in KEEP_IN_INBOX:
        return True
    tier = get_tier_for_label(label)
    tier_config = get_tier_config(tier)
    return tier_config.keep_in_inbox


def is_time_sensitive(label: str) -> bool:
    """Check if a label is time-sensitive (should escalate with age)."""
    rule = LABEL_RULES.get(label, {})
    return rule.get("time_sensitive", False)


# ============================================================================
# TIME-BASED ESCALATION
# ============================================================================

@dataclass
class EscalationResult:
    """Result of checking if an email should be escalated."""
    should_escalate: bool
    original_tier: int
    escalated_tier: int
    reason: str


def escalate_by_age(
    current_tier: int,
    email_age_hours: float,
    is_time_sensitive: bool = False,
) -> EscalationResult:
    """
    Determine if an email should be escalated based on age.

    Escalation rules:
    - < 24 hours: Keep current tier
    - 24-72 hours: Tier 3-4 -> Tier 2 (if time-sensitive)
    - > 72 hours: Tier 2-4 -> Tier 1 (always escalate old emails)

    Args:
        current_tier: Current priority tier (1-4)
        email_age_hours: Age of the email in hours
        is_time_sensitive: Whether the email's category is time-sensitive

    Returns:
        EscalationResult with escalation details
    """
    # Tier 1 (Critical) cannot be escalated further
    if current_tier == 1:
        return EscalationResult(
            should_escalate=False,
            original_tier=1,
            escalated_tier=1,
            reason="Already at highest priority",
        )

    # < 24 hours: no escalation
    if email_age_hours < 24:
        return EscalationResult(
            should_escalate=False,
            original_tier=current_tier,
            escalated_tier=current_tier,
            reason="Email is less than 24 hours old",
        )

    # 24-72 hours: escalate Tier 3-4 to Tier 2 (if time-sensitive)
    if 24 <= email_age_hours < 72:
        if is_time_sensitive and current_tier >= 3:
            return EscalationResult(
                should_escalate=True,
                original_tier=current_tier,
                escalated_tier=2,
                reason=f"Time-sensitive email is {email_age_hours:.0f} hours old",
            )
        return EscalationResult(
            should_escalate=False,
            original_tier=current_tier,
            escalated_tier=current_tier,
            reason="Not time-sensitive or already Important tier",
        )

    # > 72 hours: escalate anything below Tier 1 to Tier 1
    if email_age_hours >= 72:
        return EscalationResult(
            should_escalate=True,
            original_tier=current_tier,
            escalated_tier=1,
            reason=f"Email is {email_age_hours:.0f} hours old (>72h)",
        )

    return EscalationResult(
        should_escalate=False,
        original_tier=current_tier,
        escalated_tier=current_tier,
        reason="No escalation rule matched",
    )


def calculate_email_age_hours(email_date: Optional[datetime]) -> float:
    """
    Calculate the age of an email in hours.

    Args:
        email_date: The email's received date

    Returns:
        Age in hours, or 0 if date is None
    """
    if email_date is None:
        return 0

    # Ensure we compare timezone-aware datetimes
    now = datetime.now(timezone.utc)
    if email_date.tzinfo is None:
        # Assume UTC if no timezone
        email_date = email_date.replace(tzinfo=timezone.utc)

    age = now - email_date
    return age.total_seconds() / 3600
