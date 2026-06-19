[![ORGAN-III: Ergon](https://img.shields.io/badge/ORGAN--III-Ergon-1b5e20?style=flat-square)](https://github.com/organvm-iii-ergon)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

# Universal Mail Automation

[![CI](https://github.com/organvm-iii-ergon/universal-mail--automation/actions/workflows/ci.yml/badge.svg)](https://github.com/organvm-iii-ergon/universal-mail--automation/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey)](https://github.com/organvm-iii-ergon/universal-mail--automation)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/organvm-iii-ergon/universal-mail--automation/blob/main/LICENSE)
[![Organ III](https://img.shields.io/badge/Organ-III%20Ergon-F59E0B)](https://github.com/organvm-iii-ergon)
[![Status](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/organvm-iii-ergon/universal-mail--automation)
[![Python](https://img.shields.io/badge/lang-Python-informational)](https://github.com/organvm-iii-ergon/universal-mail--automation)


**Multi-provider inbox triage with provable restraint: one rules engine for Gmail, Outlook, IMAP/iCloud, and macOS Mail, plus a fail-closed protected-sender gate and signed audit receipts.**

---

## Table of Contents

- [The Problem](#the-problem)
- [What It Is](#what-it-is)
- [Product Overview](#product-overview)
- [Who Pays](#who-pays)
- [Cloudflare Share Demo](#cloudflare-share-demo)
- [Technical Architecture](#technical-architecture)
  - [System Diagram](#system-diagram)
  - [Module Structure](#module-structure)
  - [Provider Abstraction Layer](#provider-abstraction-layer)
  - [Rules Engine](#rules-engine)
  - [Eisenhower Priority Tier System](#eisenhower-priority-tier-system)
  - [VIP Sender System](#vip-sender-system)
  - [Time-Based Escalation](#time-based-escalation)
  - [State Management and Crash Recovery](#state-management-and-crash-recovery)
  - [Data Models](#data-models)
- [Installation and Quick Start](#installation-and-quick-start)
  - [Prerequisites](#prerequisites)
  - [Install from PyPI](#install-from-pypi)
  - [Install from Source](#install-from-source)
  - [Local On-Demand Intake](#local-on-demand-intake)
  - [Optional macOS Scheduling](#optional-macos-scheduling)
  - [First Run](#first-run)
- [Usage](#usage)
- [CLI Reference](#cli-reference)
  - [Labeling Commands](#labeling-commands)
  - [Reporting Commands](#reporting-commands)
  - [Triage Commands](#triage-commands)
  - [Health and Diagnostics](#health-and-diagnostics)
- [Configuration](#configuration)
  - [Configuration Precedence](#configuration-precedence)
  - [YAML Configuration File](#yaml-configuration-file)
  - [Environment Variables](#environment-variables)
  - [Auth Service and Legacy 1Password](#auth-service-and-legacy-1password)
  - [Adding Custom Rules](#adding-custom-rules)
  - [Configuring VIP Senders](#configuring-vip-senders)
- [Provider Capabilities Matrix](#provider-capabilities-matrix)
- [Pricing and Monetization](#pricing-and-monetization)
- [Label Taxonomy](#label-taxonomy)
- [Scheduling and Daily Automation](#scheduling-and-daily-automation)
- [Cross-Organ Context](#cross-organ-context)
- [Related Work](#related-work)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## The Problem

**Email chaos is universal.** Anyone who operates across multiple accounts — a personal Gmail, a work Outlook, an iCloud account for Apple devices — knows the friction. Important messages drown in newsletter noise. Financial alerts compete with marketing spam. Each provider offers its own filter system, but none of them talk to each other. The result is fragmented organization, duplicated effort, and the persistent anxiety of missing something critical.

Manual approaches fail at scale. "Touch It Once" and "Inbox Zero" philosophies demand a human decision on every single email, which breaks down above a few hundred messages per day. Gmail filters cannot share logic with Outlook rules. iCloud rules cannot reference Gmail labels. The organizational schemes diverge, and the user is left maintaining three separate systems that accomplish the same goal badly.

This project eliminates that fragmentation. One set of categorization rules. One priority system. One CLI. Every provider.

---

## What It Is

Universal Mail Automation is a local-first email triage product that turns provider-specific inbox rules into one portable decision layer. It connects to Gmail, Outlook.com, standard IMAP/iCloud, and macOS Mail.app, normalizes messages into shared dataclasses, applies one categorization taxonomy, and then translates the result back into provider-native labels, folders, categories, stars, and archive actions.

The product is built around restraint, not just automation. Government, financial, legal, platform/security, and user-configured protected senders are held in the inbox by a fail-closed gate. Apply runs can write an independent audit receipt, and the API refuses to report success if the receipt shows a protected sender left the inbox.

It ships as:

- **`umail` / `cli.py`** for local operators who want dry-runs, labels, tier routing, summaries, pending lists, VIP checks, and draft-oriented triage.
- **FastAPI endpoints** for hosted preview/live triage, billing, account entitlements, audit receipts, and protected-sender checks.
- **MCP tools** for agents that need safe mailbox triage without raw archive/delete access.
- **ACP checkout endpoints** for agents buying prepaid verified-safe triage runs.

---

## Product Overview

Universal Mail Automation is a Python-based email triage system that applies a unified set of categorization rules across Gmail (via REST API), Outlook.com (via Microsoft Graph API), iCloud and any standard IMAP server, and macOS Mail.app (via AppleScript). The system operates on three coordinated principles:

1. **Unified Rules Engine** — A single taxonomy of 28 hierarchical categories (`Dev/GitHub`, `Finance/Banking`, `AI/Services`, `Travel`, `Marketing`, etc.) defined as regex patterns in `core/rules.py`. Define a rule once, and it applies to every provider.

2. **Eisenhower Matrix Prioritization** — Every email is assigned to one of four priority tiers (Critical, Important, Delegate, Reference) that determine whether it stays in the inbox, gets archived, gets starred, or simply gets categorized for later retrieval.

3. **Time-Based Escalation** — Emails that remain unprocessed age into higher priority tiers. A Tier 4 (Reference) email that sits for 72+ hours automatically escalates to Tier 1 (Critical), ensuring nothing falls through the cracks.

4. **Protected-Sender Gate** — Known-sensitive mail is never archived or moved out of the inbox. Empty or unparseable senders are treated as protected, so uncertainty fails closed.

5. **Signed Audit Receipts** — Local, API, MCP, and ACP paths can emit receipts that prove what was held, what was moved, and whether any protected-sender invariant was violated.

The system is designed for daily intake, but the primary local path is on-demand. Use `scripts/intake_now.sh` to create/reuse the venv, verify Gmail auth, and write private triage reports under user-local state. A macOS `launchd` job is available only as an explicit opt-in for machines where LaunchAgents are allowed.

---

## Who Pays

The free product is for a person running safe triage on one Gmail inbox. The paid product is for reach and evidence: more providers, more live runs, scheduled automation, retained receipts, team mailboxes, and agent access. The safety floor is identical on every tier.

| Buyer | Why they pay | Best fit |
|-------|--------------|----------|
| Single-inbox self-hoster | Wants dry-runs, protected-sender safety, and Gmail categorization without a subscription. | Free / Self-host |
| Multi-account operator | Runs personal Gmail, work Outlook, iCloud, and/or Mail.app through one taxonomy and wants scheduled triage plus retained receipts. | Pro |
| Team or compliance-heavy workflow | Needs multi-mailbox policy, retained receipt history, exports, priority support, and account-level controls. | Business |
| AI agent / automation buyer | Needs a safe triage tool-call that cannot silently archive protected mail and can produce proof per run. | Metered runs or ACP credit packs |

The monetization boundary is deliberate: Universal Mail Automation charges for run volume, connected-provider reach, agent access, and receipt retention. It does not charge extra for the protected-sender gate or the audit receipt.

---

## Cloudflare Share Demo

A public Cloudflare Worker demo is available for quick partner review:

- Live share URL: <https://uma.4444j99.dev>
- Deployment note: [docs/cloudflare-share-demo.md](docs/cloudflare-share-demo.md)

This share surface serves the dashboard and a minimal same-origin API. It is not the canonical product backend; the Python application remains authoritative for real provider operations.

---

## Technical Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                          cli.py                                  │
│    Unified CLI: label | summary | pending | vip | escalate       │
│    --provider {gmail,outlook,imap,mailapp}                       │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────────┐
│                       core/ layer                                │
│  ┌──────────────┐  ┌────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  rules.py    │  │ config.py  │  │ state.py │  │ models.py │  │
│  │  LABEL_RULES │  │ YAML/env   │  │ crash    │  │ dataclass │  │
│  │  PRIORITY    │  │ precedence │  │ recovery │  │ contracts │  │
│  │  VIP_SENDERS │  │            │  │          │  │           │  │
│  └──────────────┘  └────────────┘  └──────────┘  └───────────┘  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
    ┌──────────────────────┼───────────────────────┐
    │                      │                       │
    ▼                      ▼                       ▼
┌──────────┐       ┌────────────┐          ┌────────────┐
│  Gmail   │       │  Outlook   │          │ IMAP/Mail  │
│  REST    │       │  Graph     │          │  .app      │
│  API     │       │  API       │          │            │
│          │       │            │          │            │
│ Batch    │       │ Categories │          │ X-GM-LABELS│
│ Modify   │       │ Folders    │          │ AppleScript│
│ Labels   │       │ Flagging   │          │ Folders    │
└──────────┘       └────────────┘          └────────────┘
```

### Module Structure

```
universal-mail--automation/
├── cli.py                          # Unified CLI entry point (argparse)
├── core/                           # Shared components
│   ├── __init__.py
│   ├── rules.py                    # LABEL_RULES taxonomy, categorize_message(),
│   │                               #   PRIORITY_TIERS, VIP_SENDERS, escalation
│   ├── config.py                   # Multi-source config: YAML > env > defaults
│   ├── state.py                    # StateManager for crash recovery (JSON persistence)
│   └── models.py                   # EmailMessage, LabelAction, ProcessingResult dataclasses
├── providers/                      # Email service adapters
│   ├── __init__.py
│   ├── base.py                     # Abstract EmailProvider + ProviderCapabilities flags
│   ├── gmail.py                    # Gmail REST API with batch operations
│   ├── outlook.py                  # Microsoft Graph API with MSAL auth
│   ├── imap.py                     # Generic IMAP + Gmail X-GM-LABELS extension
│   └── mailapp.py                  # macOS Mail.app via AppleScript subprocess
├── auth/                           # Authentication helpers
│   ├── __init__.py
│   ├── service.py                  # Tokenized encrypted secret store
│   └── onepassword.py              # Legacy 1Password CLI integration for secrets
├── deploy.sh                       # macOS setup script (venv; launchd opt-in only)
├── scripts/intake_now.sh           # On-demand Gmail intake runner
├── run_automation.sh               # Daily runner script (all providers)
├── seed.yaml                       # Project metadata and AI agent contract
├── requirements.txt                # Python dependencies
├── com.user.mail_automation.plist  # macOS LaunchAgent schedule definition
└── *.py / *.applescript            # Legacy and utility scripts
```

### Provider Abstraction Layer

The architecture is built around an abstract `EmailProvider` base class (`providers/base.py`) that defines a uniform interface for all email services. Each provider implements the same set of methods — `connect()`, `disconnect()`, `list_messages()`, `get_message_details()`, `apply_label()`, `remove_label()`, `archive()`, `star()`, `ensure_label_exists()`, and `apply_actions()` — adapting them to the underlying API's semantics.

A `ProviderCapabilities` flag enum describes what each provider supports. This allows the core logic to make runtime decisions: Gmail supports true multi-label semantics and batch operations; Outlook supports color categories and folder hierarchies; IMAP supports Gmail extensions when configured; Mail.app supports folders and flagging via AppleScript.

The provider factory function in `cli.py` instantiates the correct provider from a `--provider` argument, and every provider supports the context manager protocol (`with provider:`) for clean connection lifecycle management.

### Rules Engine

The rules engine (`core/rules.py`) is the heart of the system. It defines a `LABEL_RULES` dictionary with 28 categories, each containing:

- **`patterns`** — A list of regex patterns matched against the combined sender + subject text of each email.
- **`priority`** — A numeric ordering (lower = matched first) that resolves conflicts when multiple rules match. First match wins.
- **`tier`** — The Eisenhower tier (1–4) assigned to emails matching this rule.
- **`time_sensitive`** — A boolean flag that determines whether the email is eligible for time-based escalation.

The `categorize_with_tier()` function is the primary entry point. It checks VIP senders first (always override normal rules), then performs pattern matching across all rules, returning a `CategorizationResult` dataclass that packages the label, tier, time sensitivity flag, and VIP metadata together.

Pattern matching uses `re.search` with `re.IGNORECASE` against a combined lowercase string of sender and subject, ensuring broad matching without requiring exact-match configurations.

### Eisenhower Priority Tier System

Every email receives one of four Eisenhower tiers, each with distinct behavioral consequences:

| Tier | Name | Color | Inbox | Star | Folder | Description |
|------|------|-------|:-----:|:----:|--------|-------------|
| 1 | Critical | Red | Yes | Yes | `Action/Critical` | Financial alerts, security notifications, government correspondence, personal/family emails. Demands immediate attention. |
| 2 | Important | Yellow | Yes | No | `Action/Important` | Code reviews, payment confirmations, health matters, job opportunities, domain renewals, travel confirmations. Should be addressed same-day. |
| 3 | Delegate | Blue | No | No | `Action/Delegate` | Infrastructure alerts, AI service notifications, social media, educational content. Can be reviewed during dedicated triage time. |
| 4 | Reference | Green | No | No | *(category only)* | Shopping confirmations, entertainment, marketing, newsletters. Archived and categorized for retrieval if needed. |

Each tier is encoded as a frozen `PriorityTier` dataclass with `keep_in_inbox`, `star`, `folder`, and `color` attributes. The provider implementations translate these into provider-specific actions: Gmail labels + archive, Outlook color categories + folder moves, IMAP flags + folder copies.

### VIP Sender System

VIP senders bypass the normal categorization pipeline entirely. When a sender matches a VIP pattern, the system uses the VIP's configured tier and starring behavior regardless of which category rule would normally match. VIP senders can optionally override the label assignment itself via `label_override`, or allow normal categorization to proceed while simply forcing the tier upward.

VIP senders are configured in two ways:
1. **At runtime** via `add_vip_sender()` in `core/rules.py` (for programmatic use).
2. **Via YAML config** at `~/.config/mail_automation/config.yaml` under the `vip_senders` key, loaded at startup by `apply_vip_senders_from_config()`.

### Time-Based Escalation

The `escalate_by_age()` function implements automatic priority escalation based on email age:

- **< 24 hours** — No escalation. The original tier stands.
- **24–72 hours** — Tier 3 and Tier 4 emails escalate to Tier 2, but only if their category is marked `time_sensitive`.
- **> 72 hours** — Any email below Tier 1 escalates to Tier 1 (Critical). If an email has been sitting for three days, something is wrong.

The `escalate` CLI command applies this logic across the inbox, re-triaging stale emails. It uses `calculate_email_age_hours()` to compute age from the message's received date, handling timezone-aware and timezone-naive datetimes.

### State Management and Crash Recovery

The `StateManager` class (`core/state.py`) persists processing state to a JSON file after each batch. It stores:

- **`next_page_token`** — The pagination token for resuming from the last processed page.
- **`total_processed`** — Running count of processed messages.
- **`history`** — A dictionary mapping label names to counts (for reporting).
- **`last_run`** — ISO 8601 timestamp of the last run.
- **`provider`** — Which provider was being processed.

If the automation crashes mid-run (network failure, API rate limit exhaustion, system sleep), the next invocation picks up from the saved page token. Each provider has its own state file (`gmail_state.json`, `outlook_state.json`, etc.), allowing independent recovery.

### Data Models

The `core/models.py` module defines three provider-agnostic dataclasses:

- **`EmailMessage`** — An immutable representation of an email with `id`, `sender`, `subject`, `date`, `labels`, `is_read`, `is_starred`, `priority_tier`, and `categories`. The `combined_text` property returns a lowercase concatenation of sender and subject for pattern matching.

- **`LabelAction`** — Accumulates multiple actions (add labels, remove labels, archive, star, set category, set folder, set due date) for a single message. Supports `merge()` for combining overlapping actions.

- **`ProcessingResult`** — Aggregates statistics from a batch operation: `processed_count`, `success_count`, `error_count`, `label_counts` dictionary, and an `errors` list.

---

## Installation and Quick Start

Commands below use the installed `umail` console script. From a source checkout,
`python3 cli.py ...` accepts the same arguments.

### Prerequisites

- Python 3.9+ for the core/Gmail CLI; Python 3.10+ for the MCP server.
- Provider credentials for the mailboxes you connect:
  - Gmail API OAuth client/token material for Gmail.
  - Azure app registration for Outlook.com / Microsoft Graph.
  - IMAP host/user/app password for iCloud or standard IMAP.
  - macOS Mail.app access only when using the Mail.app provider.
- 1Password CLI (`op`) is recommended for local secret loading.
- No license key is required for the Free/Self-host Gmail path. The local CLI
  treats a missing `UMAIL_LICENSE_KEY` as Free: Gmail only, with large `--limit`
  values reduced to the free safety cap. Non-Gmail local providers require a
  signed Pro license; hosted API accounts use the billing entitlements described
  in [Pricing and Monetization](#pricing-and-monetization).

### Install from PyPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install universal-mail-automation

umail --version
umail health --provider gmail
```

The base install keeps dependencies lean and targets Gmail. Add extras when you
need other surfaces:

| Extra | Adds | Install |
|-------|------|---------|
| `outlook` | Outlook.com / Microsoft Graph | `pip install "universal-mail-automation[outlook]"` |
| `yaml` | `~/.config/mail_automation/config.yaml` support | `pip install "universal-mail-automation[yaml]"` |
| `api` | FastAPI HTTP surface + Stripe billing | `pip install "universal-mail-automation[api]"` |
| `mcp` | MCP server (`umail-mcp`, Python 3.10+) | `pip install "universal-mail-automation[mcp]"` |
| `all` | Outlook, YAML, and API dependencies | `pip install "universal-mail-automation[all]"` |

### Install from Source

```bash
git clone https://github.com/organvm-iii-ergon/universal-mail--automation.git
cd universal-mail--automation

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"

pytest -q
```

Use this path when you are changing rules, providers, billing/API code, or the
agent-commerce surfaces. See [INSTALL.md](INSTALL.md) for package extras, macOS
bundle details, and release-build commands.

### Local On-Demand Intake

This machine's home-level agent policy forbids LaunchAgents. The safe default is
the on-demand intake runner:

```bash
scripts/intake_now.sh
```

The runner:

1. Creates `.venv/` if it is missing
2. Installs the core, API, and MCP dependency sets
3. Loads `~/.config/op/mail_automation.env.op.sh`
4. Runs `cli.py health --provider gmail`
5. Writes private reports under `~/.local/state/universal-mail-automation/intake/`
6. Does **not** install, load, or modify LaunchAgents

The most useful output files are:

- `*-reply-needed.md` — recent human/action-oriented mail and suggested replies
- `*-drafts.md` — stuck drafts from the last 30 days
- `*-gmail-risk.md` — broader two-week risk/payment/security/provider queue

### Optional macOS Scheduling

The `deploy.sh` script handles the legacy local setup and can optionally install
a macOS `launchd` schedule:

```bash
./deploy.sh
```

This will:
1. Create a Python virtual environment at `.venv/`
2. Install all dependencies from `requirements.txt` (plus `msal` and `requests` for Outlook)
3. Make `run_automation.sh` executable
4. Create the log directory at `~/System/Logs/mail_automation/`
5. Skip LaunchAgent installation unless explicitly requested

To opt into launchd on a machine where that is allowed:

```bash
INSTALL_LAUNCH_AGENT=1 ./deploy.sh
```

### First Run

```bash
# Load secrets (1Password integration)
source ~/.config/op/mail_automation.env.op.sh

# Verify the connection
umail health --provider gmail

# Preview changes; no mailbox modifications and no receipt file
umail label --provider gmail --query "has:nouserlabels" --limit 25 --dry-run

# Apply labels to unlabeled Gmail messages; appends audit/gmail-triage.jsonl
umail label --provider gmail --query "has:nouserlabels" --limit 100 --redact-audit

# Summarize the current mailbox by priority tier
umail summary --provider gmail --format markdown
```

Multi-provider examples for licensed local use or hosted Pro/Business accounts:

```bash
# Outlook categories + Action folders
umail label --provider outlook --tier-routing --dry-run

# iCloud or another IMAP provider
umail label --provider imap --host imap.mail.me.com --dry-run

# macOS Mail.app
umail label --provider mailapp --account "iCloud" --dry-run

# Run all providers sequentially
./run_automation.sh
```

---

## Usage

Start with `--dry-run` on any new query, rule change, provider, or mailbox. A
dry-run previews the category/routing decisions without applying labels, moving
mail, or writing a CLI receipt. Live `label` and `escalate` runs write an
append-only receipt under `audit/` by default; pass `--redact-audit` when the
receipt may be shared outside your machine.

Common workflows:

```bash
# Categorize unlabelled Gmail mail
umail label --provider gmail --query "has:nouserlabels" --limit 100

# Re-triage stale messages and raise their priority when age rules trigger
umail escalate --provider gmail --query "in:inbox" --dry-run

# Route messages by Eisenhower tier when the provider supports folders/categories
umail label --provider outlook --tier-routing

# Inspect high-priority and VIP work queues
umail pending --provider gmail --format markdown
umail vip --provider gmail --format table

# Research, rank, and optionally draft replies
umail triage --provider gmail --top 20 --draft --name "Your Name"
```

Hosted/API usage:

```bash
# Run the API locally
uvicorn api.app:app --reload

# Preview a triage run without modifying mail
curl -s localhost:8000/v1/triage/preview \
  -H 'content-type: application/json' \
  -d '{"provider":"gmail","query":"has:nouserlabels","limit":50}'

# Expose local MCP tools over stdio
python -m mcp_server
```

See [api/README.md](api/README.md) for HTTP examples and
[docs/agent-commerce.md](docs/agent-commerce.md) for MCP and ACP details.

---

## CLI Reference

The CLI (`cli.py`) is built on `argparse` and provides six subcommands, each accepting a `--provider` flag to target a specific email service.

### Labeling Commands

```bash
# Label unlabeled Gmail emails
python3 cli.py label --provider gmail

# Label with a custom query
python3 cli.py label --provider gmail --query "from:important@example.com"

# With Eisenhower tier routing (Outlook categories + Action folders)
python3 cli.py label --provider outlook --tier-routing

# VIP senders only (skip normal categorization)
python3 cli.py label --provider gmail --vip-only

# Re-label emails currently tagged Misc/Other
python3 cli.py label --provider gmail --query "label:Misc/Other" --remove-label "Misc/Other"

# Dry run — preview all changes without applying them
python3 cli.py label --provider outlook --dry-run
```

### Reporting Commands

```bash
# Summary by priority tier
python3 cli.py summary --provider gmail

# Pending items needing action (Tier 1 and 2)
python3 cli.py pending --provider outlook

# VIP sender activity report
python3 cli.py vip --provider gmail

# Re-triage stale emails via time-based escalation (dry run)
python3 cli.py escalate --provider outlook --dry-run

# Re-triage and apply escalations
python3 cli.py escalate --provider gmail
```

### Triage Commands

```bash
# Research, prioritize, and rank the mailbox (top 20 items)
python3 cli.py triage --provider gmail --top 20

# Triage with voice-matched reply drafts for items needing a response
python3 cli.py triage --provider gmail --top 20 --draft --name "Anthony"

# On-demand recent intake reports for this local machine
scripts/intake_now.sh

# Use a saved voice profile / sent-mail corpus for drafting
python3 cli.py triage --provider gmail --draft \
    --voice-file ~/.config/mail_automation/voice.json \
    --samples-file ~/.config/mail_automation/sent_samples.txt

# Machine-readable output for downstream tooling
python3 cli.py triage --provider outlook --format json --limit 100
```

### Health and Diagnostics

```bash
# Provider health check (verifies connection and credentials)
python3 cli.py health --provider gmail

# Full diagnostic report
python3 cli.py report --provider outlook
```

---

## Configuration

### Configuration Precedence

The system loads configuration from multiple sources with clear precedence (highest wins):

1. **CLI arguments** — `--provider`, `--query`, `--dry-run`, etc.
2. **Environment variables** — Prefixed with `MAIL_AUTO_` (e.g., `MAIL_AUTO_DEFAULT_PROVIDER`)
3. **YAML config file** — `~/.config/mail_automation/config.yaml`
4. **Built-in defaults** — Defined in `core/config.py` dataclasses

The config file is located by checking, in order:
1. `MAIL_AUTOMATION_CONFIG` environment variable
2. `~/.config/mail_automation/config.yaml`
3. `~/.mail_automation.yaml`
4. `mail_automation.yaml` in the working directory

### YAML Configuration File

```yaml
# ~/.config/mail_automation/config.yaml

default_provider: gmail
log_level: INFO
batch_size: 100
throttle_seconds: 1.0

gmail:
  enabled: true
  default_query: "has:nouserlabels"
  state_file: "gmail_state.json"

imap:
  enabled: true
  host: imap.mail.me.com
  port: 993
  use_gmail_extensions: false

outlook:
  enabled: true
  state_file: "outlook_state.json"

mailapp:
  enabled: true
  account: "iCloud"
  default_mailbox: "INBOX"
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MAIL_AUTO_DEFAULT_PROVIDER` | Default provider when `--provider` is omitted | `gmail` |
| `MAIL_AUTO_LOG_LEVEL` | Logging verbosity | `INFO` |
| `MAIL_AUTO_DRY_RUN` | Enable dry-run mode globally | `false` |
| `MAIL_AUTO_BATCH_SIZE` | Messages per processing batch | `100` |
| `IMAP_HOST` | IMAP server hostname | `imap.gmail.com` |
| `IMAP_USER` | IMAP username | *(required)* |
| `IMAP_PASS` | IMAP password | *(via 1Password)* |
| `OUTLOOK_CLIENT_ID` | Azure app registration client ID | *(required)* |
| `OUTLOOK_TOKEN_CACHE` | Path to Outlook token cache file | `~/.outlook_token_cache.json` |

### Auth Service and Legacy 1Password

`auth/service.py` provides the replacement path for env/1Password credential
loading: secrets are stored behind opaque `uma_auth_*` tokens in an encrypted
SQLite store under `data/` by default, with monthly data-key rotation. Providers
still use the legacy environment/1Password model until they are wired to resolve
these tokens at `connect()` time.

| Variable | Purpose | Default |
|----------|---------|---------|
| `UMA_AUTH_STORE_PATH` | SQLite path for tokenized auth secrets | `data/auth_service.db` |
| `UMA_AUTH_KEY_PATH` | Local master-key file when `UMA_AUTH_MASTER_KEY` is unset | `data/auth_service.key` |
| `UMA_AUTH_MASTER_KEY` | Optional base64 master key from `auth.service.generate_master_key()` | *(generated key file)* |

Legacy secrets are loaded from 1Password via environment variables, typically
sourced from a shell script:

```bash
# ~/.config/op/mail_automation.env.op.sh
export GMAIL_OAUTH_OP_REF="op://Vault/Gmail OAuth/client_json"
export GMAIL_TOKEN_OP_REF="op://Vault/Gmail OAuth/token_json"
export ICLOUD_IMAP_HOST="imap.mail.me.com"
export ICLOUD_IMAP_USER="user@icloud.com"
export ICLOUD_IMAP_PASS="$(op read 'op://Vault/iCloud App Password/password')"
export OUTLOOK_CLIENT_ID="your-azure-app-client-id"
```

The IMAP provider also supports direct 1Password CLI lookup via `OP_ACCOUNT`, `OP_ITEM`, and `OP_FIELD` environment variables, calling `op item get` at connection time.

### Adding Custom Rules

Edit `core/rules.py` to add categories:

```python
"NewCategory/Subcategory": {
    "patterns": [r"sender\.com", r"keyword.*pattern"],
    "priority": 10,        # Lower = matched first
    "tier": 2,             # Eisenhower tier (1-4)
    "time_sensitive": True, # Eligible for escalation
}
```

Or add rules via YAML config without modifying source code:

```yaml
custom_rules:
  "Custom/Category":
    patterns:
      - "custom-pattern"
      - "another-pattern"
    priority: 5
    tier: 2
    time_sensitive: true
```

### Configuring VIP Senders

Via YAML config:

```yaml
vip_senders:
  "ceo@company.com":
    pattern: "ceo@company\\.com"
    tier: 1
    star: true
    note: "CEO"
  "important-client":
    pattern: ".*@important-client\\.com"
    tier: 1
    star: true
    label_override: "Personal"
    note: "Important client domain"
```

---

## Provider Capabilities Matrix

| Feature | Gmail API | Outlook Graph | IMAP (Standard) | IMAP (Gmail Ext.) | Mail.app |
|---------|:---------:|:------------:|:---------------:|:-----------------:|:--------:|
| True labels (multiple per message) | Yes | No | No | Yes | No |
| Folders | No | Yes | Yes | Yes | Yes |
| Color categories | No | Yes | No | No | No |
| Star / Flag | Yes | Yes (+ due dates) | Yes | Yes | Yes |
| Archive | Yes | Yes | Yes (copy + delete) | Yes | Yes |
| Batch operations | Yes (1000/batch) | No | No | No | No |
| Server-side search | Yes | Yes (OData) | Yes (IMAP SEARCH) | Yes | No |
| OAuth / modern auth | Yes | Yes (MSAL) | Varies | N/A | N/A |
| Context manager | Yes | Yes | Yes | Yes | Yes |

The Gmail provider is the most capable, supporting batch `batchModify` operations that can apply labels to up to 1,000 messages in a single API call. It also implements exponential backoff with retry logic for `rateLimitExceeded`, `userRateLimitExceeded`, and `quotaExceeded` errors, with a configurable base delay starting at 10 seconds.

The Outlook provider uniquely supports **color categories** (25 preset colors) and **due-date flagging** that syncs with Microsoft To Do, enabling task management integration. It handles hierarchical folder creation automatically, creating nested folder paths like `Action/Critical` by walking the path segments.

---

## Pricing and Monetization

**Sold on the negative guarantee, not features.** The fail-closed
protected-sender gate and the independent signed audit receipt are identical on
every tier, including Free. The business model charges for reach, retained
evidence, and agent access.

The canonical plan catalog lives in [api/plans.py](api/plans.py). The generated
human-readable artifact is [pricing.md](pricing.md), and hosted deployments
expose the same catalog at `GET /v1/billing/plans`.

| Plan | Price | Reach | Receipt retention | Who pays |
|------|-------|-------|-------------------|----------|
| **Free / Self-host** | $0 | Gmail provider; 50 hosted live triage runs/month; unlimited dry-runs | Downloadable run receipt only; no hosted ledger | Single-inbox self-hosters and evaluators |
| **Pro** | $19/mo | All providers; 5,000 hosted live triage runs/month; scheduled/recurring triage + webhooks | Downloadable signed receipts + 90-day hosted ledger | Multi-account operators who want every inbox behind one taxonomy |
| **Business** | $49/mo | All providers; unlimited live triage runs; multi-mailbox/team policy | 1-year retained signed-receipt history with compliance export | Teams, compliance workflows, and agent-enabled operations |

Agent and usage-based monetization:

| Path | Price | Use case |
|------|-------|----------|
| **Metered agent runs** | $0.01 / triage run | MCP tool calls and usage-metered hosted automation |
| **ACP credit pack** | 100 runs for $1.00 | One-time delegated agent purchase through Agentic Commerce Protocol |
| **ACP credit pack** | 1,000 runs for $9.00 | Discounted one-time delegated agent purchase |

Human subscriptions are handled through Stripe Checkout and the self-serve
Customer Portal (`/v1/billing/checkout`, `/v1/billing/portal`) on configured
deployments. Agent purchases use ACP endpoints under `/acp/checkout_sessions`
because delegated ACP payments are one-time credit purchases, not recurring
subscriptions.

---

## Label Taxonomy

The 28 built-in categories span the full spectrum of email types:

| Category | Tier | Time-Sensitive | Example Patterns |
|----------|:----:|:--------------:|-----------------|
| `Dev/GitHub` | 2 | No | `github.com`, `notifications@github` |
| `Dev/Code-Review` | 2 | Yes | `coderabb`, `sourcery`, `copilot` |
| `Dev/Infrastructure` | 3 | No | `cloudflare`, `vercel`, `netlify` |
| `Dev/GameDev` | 3 | No | `unity3d.com`, `godotengine` |
| `AI/Services` | 3 | No | `openai`, `anthropic`, `claude` |
| `AI/Grok` | 3 | No | `grok`, `x.ai` |
| `AI/Data Exports` | 2 | Yes | `data export`, `export is ready` |
| `Finance/Banking` | 1 | Yes | `chase`, `capital one`, `experian` |
| `Finance/Payments` | 2 | Yes | `paypal`, `stripe`, `venmo` |
| `Finance/Tax` | 2 | Yes | `turbotax`, `irs.gov` |
| `Tech/Security` | 1 | Yes | `1password`, `security alert` |
| `Tech/Google` | 2 | Yes | `@google.com`, `google cloud` |
| `Shopping` | 4 | No | `amazon`, `ebay`, `walmart` |
| `Personal/Health` | 2 | Yes | `walgreens`, `cvs`, `pharmacy` |
| `Social/LinkedIn` | 3 | No | `linkedin.com` |
| `Travel` | 2 | Yes | `united.com`, `airbnb`, `booking.com` |
| `Entertainment` | 4 | No | `netflix`, `spotify`, `audible` |
| `Education/Research` | 3 | No | `coursera`, `arxiv`, `academia.edu` |
| `Professional/Jobs` | 2 | Yes | `indeed`, `glassdoor`, `linkedin jobs` |
| `Professional/Legal` | 2 | Yes | `legalzoom`, `attorney` |
| `Services/Domain` | 2 | Yes | `namecheap`, `godaddy` |
| `Tech/Storage` | 3 | No | `filerev`, `box.com`, `onedrive` |
| `Notification` | 3 | No | `notification`, `alert`, `reminder` |
| `Marketing` | 4 | No | `unsubscribe`, `newsletter`, `promo` |
| `Personal/Government` | 1 | Yes | `.gov`, `passport`, `dmv` |
| `Personal` | 1 | Yes | family-specific patterns |
| `Awaiting Reply` | 2 | Yes | `awaiting reply`, `pending response` |
| `Misc/Other` | 4 | No | `.*` (catch-all, priority 999) |

---

## Scheduling and Daily Automation

The system includes a macOS `LaunchAgent` plist (`com.user.mail_automation.plist`) that can schedule `run_automation.sh` to execute daily at 9:00 AM, but scheduler installation is opt-in. The default local workflow is `scripts/intake_now.sh`, which runs on demand and writes private reports under `~/.local/state/universal-mail-automation/intake/`.

The daily runner processes providers in sequence:

1. **Gmail** — Labels unlabeled emails, then sweeps `Misc/Other` for re-categorization.
2. **Outlook** — Processes the full inbox with tier routing.
3. **iCloud** — Processes all messages via IMAP.

Each step runs independently (failure in one provider does not block the others), with logs written to `~/System/Logs/mail_automation/`.

The `deploy.sh` script manages setup and optional scheduler install:

```bash
# Install and opt into scheduling
INSTALL_LAUNCH_AGENT=1 ./deploy.sh

# Preferred local on-demand intake
scripts/intake_now.sh

# Check scheduler status
launchctl list | grep mail_automation

# View logs
tail -f ~/System/Logs/mail_automation/launchd.stdout.log

# Unload scheduler
launchctl bootout gui/$(id -u)/com.user.mail_automation
```

---

## Cross-Organ Context

Universal Mail Automation sits within **ORGAN-III (Ergon)** — the Commerce organ of the eight-organ creative-institutional system. ORGAN-III houses SaaS products, B2B/B2C tools, and internal productivity infrastructure. This project occupies the "internal tooling" category: a system built first for the operator's own workflow, with the architectural discipline to serve as a template or product if warranted.

**Connections across the organ system:**

- **ORGAN-I (Theoria)** — The provider abstraction pattern (abstract base class with capability flags, strategy-pattern dispatch) reflects the recursive architectural thinking documented in ORGAN-I's theory corpus. The `ProviderCapabilities` flag enum is a practical application of the compositional interface design explored in `recursive-engine`.
- **ORGAN-IV (Taxis)** — The daily scheduling via launchd, the state management for crash recovery, and the multi-source configuration precedence system are all orchestration patterns. The `StateManager` class embodies the same "resumable execution" principle that `agentic-titan` applies to AI agent workflows.
- **ORGAN-V (Logos)** — The design process behind this system — the gap analysis between iCloud filtering rules and Gmail patterns, the iterative refinement of the taxonomy, the decision to adopt the Eisenhower matrix — is documented in `PROCESS.md` and represents the kind of "building in public" narrative that ORGAN-V surfaces.

---

## Related Work

- [`organvm-iii-ergon/tab-bookmark-manager`](https://github.com/organvm-iii-ergon/tab-bookmark-manager) — Browser tab and bookmark organization (parallel information-triage problem in a different domain)
- [`organvm-iv-taxis/agentic-titan`](https://github.com/organvm-iv-taxis/agentic-titan) — AI agent orchestration framework (shares the abstract-provider + state-recovery architectural pattern)
- [`organvm-i-theoria/recursive-engine`](https://github.com/organvm-i-theoria/recursive-engine--generative-entity) — Recursive systems theory (the compositional interface pattern in `providers/base.py` is a direct descendant)

---

## Contributing

This repository is part of a coordinated multi-org system. Contributions are welcome, particularly:

- **New provider implementations** — Fastmail, ProtonMail, Yahoo Mail, or any IMAP-compatible service
- **Rule refinements** — More precise regex patterns, new categories, tier adjustments
- **Testing** — Unit tests for the rules engine and provider implementations
- **Documentation** — Usage guides, configuration examples, troubleshooting

Please open an issue before submitting large changes to discuss approach and scope.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Author

**[@4444j99](https://github.com/4444j99)**

Part of the [ORGAN-III: Ergon](https://github.com/organvm-iii-ergon) organization — Commerce, SaaS, and productivity tooling.
