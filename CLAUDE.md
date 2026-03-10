# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-provider email automation system that categorizes and archives emails using Gmail API, IMAP, macOS Mail.app, or Outlook.com. Features a unified CLI with shared categorization rules across all providers.

## Commands

### Setup
```bash
# Create venv and install dependencies
./deploy.sh

# Or manually:
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# For Outlook support:
.venv/bin/pip install msal requests

# For YAML config support:
.venv/bin/pip install pyyaml
```

### Running (Unified CLI)
```bash
# Load 1Password secrets first
source ~/.config/op/mail_automation.env.op.sh

# Gmail provider (default)
python3 cli.py label --provider gmail --query "has:nouserlabels"
python3 cli.py label --provider gmail --query "label:Misc/Other" --remove-label "Misc/Other"

# IMAP provider (with Gmail extensions)
python3 cli.py label --provider imap --host imap.gmail.com --gmail-extensions

# macOS Mail.app provider
python3 cli.py label --provider mailapp --account "iCloud"

# Outlook.com provider
python3 cli.py label --provider outlook

# Dry run (don't apply changes)
python3 cli.py label --provider gmail --dry-run

# Tier-based routing (Eisenhower matrix with categories + Action folders)
python3 cli.py label --provider outlook --tier-routing

# Process only VIP sender emails
python3 cli.py label --provider gmail --vip-only

# Health check
python3 cli.py health --provider gmail

# Report (label counts)
python3 cli.py report --provider gmail
```

### Triage & Reporting Commands
```bash
# Summary by priority tier
python3 cli.py summary --provider outlook
python3 cli.py summary --provider gmail --format json

# List pending/flagged items needing action
python3 cli.py pending --provider gmail
python3 cli.py pending --format markdown

# Show VIP sender activity
python3 cli.py vip --provider outlook
python3 cli.py vip --format json

# Escalate stale emails (re-triage based on age)
python3 cli.py escalate --provider outlook --dry-run
python3 cli.py escalate --provider gmail --limit 500
```

### Legacy Commands (Backward Compatible)
```bash
# Primary labeler (unlabeled emails)
python3 gmail_labeler.py

# With custom query
python3 gmail_labeler.py --query "label:Misc/Other" --remove-label "Misc/Other"

# Bulk re-labeling pass
python3 bulk_sweeper.py

# Generate label counts report
python3 recount.py > mail_report.md

# Full daily automation
./run_automation.sh
```

### Scheduling
```bash
# Deploy launchd job (runs daily at 9 AM)
./deploy.sh

# Check scheduler status
launchctl list | grep com.user.gmail_labeler
```

## Architecture

### Module Structure
```
mail_automation/
├── core/                    # Shared components
│   ├── rules.py            # LABEL_RULES, categorize_message()
│   ├── state.py            # StateManager for crash recovery
│   ├── models.py           # EmailMessage, LabelAction dataclasses
│   └── config.py           # Multi-provider configuration
├── providers/              # Email service adapters
│   ├── base.py             # Abstract EmailProvider interface
│   ├── gmail.py            # Gmail API provider
│   ├── imap.py             # Generic IMAP provider
│   ├── mailapp.py          # macOS Mail.app (AppleScript)
│   └── outlook.py          # Microsoft Graph API
├── auth/                   # Authentication utilities
│   └── onepassword.py      # 1Password CLI integration
├── cli.py                  # Unified CLI entry point
├── gmail_labeler.py        # Legacy entry point (backward compat)
├── gmail_auth.py           # Legacy Gmail auth
└── imap_rules.py           # Legacy IMAP script
```

### Provider Capabilities

| Provider | Labels | Folders | Star | Archive | Batch API | Search | Categories |
|----------|--------|---------|------|---------|-----------|--------|------------|
| Gmail    | ✓      |         | ✓    | ✓       | ✓         | ✓      |            |
| IMAP     | ✓*     | ✓       | ✓    | ✓       |           | ✓      |            |
| Mail.app |        | ✓       | ✓    | ✓       |           |        |            |
| Outlook  |        | ✓       | ✓    | ✓       |           | ✓      | ✓          |

*IMAP with `--gmail-extensions` flag

### Core Pipeline
```
core/rules.py        Shared LABEL_RULES taxonomy
      ↓
providers/*.py       Provider-specific fetch & apply
      ↓
core/state.py        Progress persistence for resumption
```

### Key Components

**core/rules.py** - Shared categorization
- `LABEL_RULES` dict: regex patterns with priority, tier, and time_sensitive fields
- `PRIORITY_TIERS`: Eisenhower matrix (1=Critical, 2=Important, 3=Delegate, 4=Reference)
- `VIP_SENDERS`: High-priority senders that override normal categorization
- `categorize_message()`: matches sender+subject against rules
- `categorize_with_tier()`: returns full tier info with `CategorizationResult`
- `escalate_by_age()`: determines if email should be escalated based on age
- `PRIORITY_LABELS`: labels that trigger starring
- `KEEP_IN_INBOX`: labels that remain in inbox (not archived)

**providers/base.py** - Abstract interface
- `EmailProvider`: base class all providers implement
- `ProviderCapabilities`: flags for feature detection
- `ListMessagesResult`: pagination support

**core/state.py** - Crash recovery
- `StateManager`: persists progress to JSON for resumption
- Supports page tokens, processed counts, label statistics

**gmail_auth.py** - 1Password-backed OAuth
- Reads client config from `GMAIL_OAUTH_OP_REF` or `GMAIL_OAUTH_JSON`
- Reads/writes token via `GMAIL_TOKEN_OP_REF` or `OP_GMAIL_TOKEN_ITEM`/`OP_GMAIL_TOKEN_FIELD`
- Auto-refreshes expired tokens and writes back to 1Password

### Label Taxonomy
Hierarchical labels with `/` separator: `Work/Dev/GitHub`, `Finance/Banking`, `AI/Services`, etc. The `Misc/Other` label is the catch-all (priority 999).

### AppleScript Tools (macOS Mail)
- `archive_old_inbox.applescript` - Archive messages >90 days old
- `export_mail_snapshot.applescript` - Export to `mail_export.tsv`
- `flag_important_senders.applescript` - Flag VIP senders
- `route_bulk_senders.applescript` - Move newsletters to folders

## Configuration

### Environment Variables (1Password - Gmail)
```bash
GMAIL_OAUTH_OP_REF="op://Vault/Gmail OAuth/client_json"
GMAIL_TOKEN_OP_REF="op://Vault/Gmail OAuth/token_json"
# Or use item/field/vault triplets:
OP_GMAIL_TOKEN_ITEM="Gmail OAuth"
OP_GMAIL_TOKEN_FIELD="token_json"
OP_GMAIL_TOKEN_VAULT="Vault"
```

### Environment Variables (IMAP)
```bash
IMAP_HOST="imap.gmail.com"
IMAP_USER="user@gmail.com"
IMAP_PASS="app-password"  # Or use 1Password
OP_ACCOUNT="my.op.com"
OP_ITEM="IMAP Password"
OP_FIELD="password"
```

### Environment Variables (Outlook)
```bash
OUTLOOK_CLIENT_ID="your-azure-app-client-id"
OUTLOOK_TOKEN_CACHE="~/.outlook_token_cache.json"
```

### Configuration File (Optional)
Create `~/.config/mail_automation/config.yaml`:
```yaml
default_provider: gmail
log_level: INFO
batch_size: 100

gmail:
  default_query: "has:nouserlabels"
  state_file: "gmail_state.json"

imap:
  host: imap.gmail.com
  use_gmail_extensions: true

mailapp:
  account: "iCloud"

outlook:
  client_id: "your-app-id"

# VIP senders - always get priority treatment
vip_senders:
  "ceo@company.com":
    pattern: "ceo@company\\.com"
    tier: 1  # Critical
    star: true
    note: "CEO"
  "important-client":
    pattern: ".*@important-client\\.com"
    tier: 1
    star: true
    label_override: "Personal"  # Optional: override categorization
    note: "Important client domain"
```

### Adding New Rules
Edit `core/rules.py` or add to config file:
```python
"NewCategory/Subcategory": {
    "patterns": [r"sender\.com", r"keyword.*pattern"],
    "priority": 10,  # Lower = higher priority
    "tier": 2,       # 1=Critical, 2=Important, 3=Delegate, 4=Reference
    "time_sensitive": True,  # Escalate if email gets old
}
```

For bulk corrections of existing `Misc/Other` items, add to `SWEEP_RULES` in `bulk_sweeper.py`.

### Priority Tier System (Eisenhower Matrix)
| Tier | Name | Color | Behavior |
|------|------|-------|----------|
| 1 | Critical | Red | Star, keep in inbox, Action/Critical folder |
| 2 | Important | Yellow | Keep in inbox, Action/Important folder |
| 3 | Delegate | Blue | Archive, Action/Delegate folder |
| 4 | Reference | Green | Archive, categorize only |

### Time-Based Escalation Rules
- < 24 hours: No escalation
- 24-72 hours: Tier 3-4 → Tier 2 (if time_sensitive=True)
- > 72 hours: Tier 2-4 → Tier 1 (always escalate)

## Coding Conventions

- Python 3.9+, 4-space indents
- Structured logging via `logger` (avoid print statements)
- Regex patterns: escape dots (`\.`) and use raw strings (`r"..."`)
- Label names: hierarchical with `/` (e.g., `Work/Dev/GitHub`)
- Providers implement `EmailProvider` abstract base class
- Use dataclasses for DTOs (`EmailMessage`, `LabelAction`)

## Files to Avoid Modifying
- `credentials.json`, `client_secret_*.json` (secrets - gitignored)
- `*.log` files (generated output)
- `*_state.json` (runtime state for resumption)
- `~/.outlook_token_cache.json` (OAuth token cache)

## Testing

```bash
# Verify imports
python3 -c "from core import LABEL_RULES, categorize_message, PRIORITY_TIERS"
python3 -c "from core import categorize_with_tier, escalate_by_age"
python3 -c "from providers.gmail import GmailProvider"
python3 -c "from providers.outlook import OutlookProvider, CATEGORY_COLORS"

# Dry run test
python3 cli.py label --provider gmail --dry-run --limit 10

# Test tier routing (Outlook)
python3 cli.py label --provider outlook --tier-routing --dry-run --limit 5

# Test escalation
python3 cli.py escalate --provider gmail --dry-run --limit 10

# Health check
python3 cli.py health --provider gmail

# Generate summary
python3 cli.py summary --provider gmail --limit 100
```

<!-- ORGANVM:AUTO:START -->
## System Context (auto-generated — do not edit)

**Organ:** ORGAN-III (Commerce) | **Tier:** standard | **Status:** PUBLIC_PROCESS
**Org:** `organvm-iii-ergon` | **Repo:** `universal-mail--automation`

### Edges
- *No inter-repo edges declared in seed.yaml*

### Siblings in Commerce
`classroom-rpg-aetheria`, `gamified-coach-interface`, `trade-perpetual-future`, `fetch-familiar-friends`, `sovereign-ecosystem--real-estate-luxury`, `public-record-data-scrapper`, `search-local--happy-hour`, `multi-camera--livestream--framework`, `mirror-mirror`, `the-invisible-ledger`, `enterprise-plugin`, `virgil-training-overlay`, `tab-bookmark-manager`, `a-i-chat--exporter`, `.github` ... and 12 more

### Governance
- Strictly unidirectional flow: I→II→III. No dependencies on Theory (I).

*Last synced: 2026-03-08T20:11:34Z*

## Session Review Protocol

At the end of each session that produces or modifies files:
1. Run `organvm session review --latest` to get a session summary
2. Check for unimplemented plans: `organvm session plans --project .`
3. Export significant sessions: `organvm session export <id> --slug <slug>`
4. Run `organvm prompts distill --dry-run` to detect uncovered operational patterns

Transcripts are on-demand (never committed):
- `organvm session transcript <id>` — conversation summary
- `organvm session transcript <id> --unabridged` — full audit trail
- `organvm session prompts <id>` — human prompts only


## Active Directives

| Scope | Phase | Name | Description |
|-------|-------|------|-------------|
| system | any | prompting-standards | Prompting Standards |
| system | any | research-standards-bibliography | APPENDIX: Research Standards Bibliography |
| system | any | research-standards | METADOC: Architectural Typology & Research Standards |
| system | any | sop-ecosystem | METADOC: SOP Ecosystem — Taxonomy, Inventory & Coverage |
| system | any | autopoietic-systems-diagnostics | SOP: Autopoietic Systems Diagnostics (The Mirror of Eternity) |
| system | any | cicd-resilience-and-recovery | SOP: CI/CD Pipeline Resilience & Recovery |
| system | any | cross-agent-handoff | SOP: Cross-Agent Session Handoff |
| system | any | document-audit-feature-extraction | SOP: Document Audit & Feature Extraction |
| system | any | essay-publishing-and-distribution | SOP: Essay Publishing & Distribution |
| system | any | market-gap-analysis | SOP: Full-Breath Market-Gap Analysis & Defensive Parrying |
| system | any | pitch-deck-rollout | SOP: Pitch Deck Generation & Rollout |
| system | any | promotion-and-state-transitions | SOP: Promotion & State Transitions |
| system | any | repo-onboarding-and-habitat-creation | SOP: Repo Onboarding & Habitat Creation |
| system | any | research-to-implementation-pipeline | SOP: Research-to-Implementation Pipeline (The Gold Path) |
| system | any | security-and-accessibility-audit | SOP: Security & Accessibility Audit |
| system | any | session-self-critique | session-self-critique |
| system | any | source-evaluation-and-bibliography | SOP: Source Evaluation & Annotated Bibliography (The Refinery) |
| system | any | stranger-test-protocol | SOP: Stranger Test Protocol |
| system | any | strategic-foresight-and-futures | SOP: Strategic Foresight & Futures (The Telescope) |
| system | any | typological-hermeneutic-analysis | SOP: Typological & Hermeneutic Analysis (The Archaeology) |
| unknown | any | gpt-to-os | SOP_GPT_TO_OS.md |
| unknown | any | index | SOP_INDEX.md |
| unknown | any | obsidian-sync | SOP_OBSIDIAN_SYNC.md |

Linked skills: evaluation-to-growth


**Prompting (Anthropic)**: context 200K tokens, format: XML tags, thinking: extended thinking (budget_tokens)

<!-- ORGANVM:AUTO:END -->


## ⚡ Conductor OS Integration
This repository is a managed component of the ORGANVM meta-workspace.
- **Orchestration:** Use `conductor patch` for system status and work queue.
- **Lifecycle:** Follow the `FRAME -> SHAPE -> BUILD -> PROVE` workflow.
- **Governance:** Promotions are managed via `conductor wip promote`.
- **Intelligence:** Conductor MCP tools are available for routing and mission synthesis.
