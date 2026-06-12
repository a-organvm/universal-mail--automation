#!/usr/bin/env bash
# Run the local Gmail intake path on demand.
#
# This intentionally does not install or touch LaunchAgents. Reports may include
# real senders and subjects, so they are written under user-local state by
# default instead of the git checkout.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
REPORT_DIR="${REPORT_DIR:-$STATE_HOME/universal-mail-automation/intake}"
ENV_FILE="${MAIL_AUTOMATION_ENV_FILE:-$HOME/.config/op/mail_automation.env.op.sh}"
NAME="${MAIL_AUTOMATION_USER_NAME:-Anthony}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"

BROAD_QUERY='newer_than:14d -from:notifications@github.com -from:noreply@github.com -category:promotions -category:social -in:spam -in:trash'
REPLY_QUERY='(label:"To Respond" OR label:"Awaiting Reply" OR label:"Triage/Action/Today" OR label:"Triage/Action/This-Week") -in:spam -in:trash'
DRAFT_QUERY='in:drafts newer_than:30d'

mkdir -p "$REPORT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -q -r "$REPO_DIR/requirements.txt" -r "$REPO_DIR/requirements-api.txt" -r "$REPO_DIR/requirements-mcp.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE" >/dev/null 2>&1

health_report="$REPORT_DIR/$STAMP-health.txt"
broad_report="$REPORT_DIR/$STAMP-gmail-risk.md"
reply_report="$REPORT_DIR/$STAMP-reply-needed.md"
draft_report="$REPORT_DIR/$STAMP-drafts.md"

(
  cd "$REPO_DIR"
  "$VENV_DIR/bin/python" cli.py health --provider gmail > "$health_report"
  "$VENV_DIR/bin/python" cli.py triage --provider gmail --query "$BROAD_QUERY" --top 40 --limit 400 --draft --name "$NAME" --format markdown > "$broad_report"
  "$VENV_DIR/bin/python" cli.py triage --provider gmail --query "$REPLY_QUERY" --top 40 --limit 400 --draft --name "$NAME" --format markdown > "$reply_report"
  "$VENV_DIR/bin/python" cli.py triage --provider gmail --query "$DRAFT_QUERY" --top 40 --limit 100 --draft --name "$NAME" --format markdown > "$draft_report"
)

cat <<EOF
Universal Mail Automation intake complete.

Health:       $health_report
Risk queue:   $broad_report
Reply queue:  $reply_report
Draft queue:  $draft_report

No LaunchAgent was installed or loaded.
EOF
