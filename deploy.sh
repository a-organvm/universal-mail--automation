#!/usr/bin/env bash
# Deploy and schedule Universal Mail Automation on macOS.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv}"
PLIST_DEST="$HOME/Library/LaunchAgents/com.user.mail_automation.plist"
LOG_DIR="$HOME/System/Logs/mail_automation"
INSTALL_LAUNCH_AGENT="${INSTALL_LAUNCH_AGENT:-0}"

echo "Deploying Universal Mail Automation from $REPO_DIR"
echo "Using Python: $PYTHON_BIN"
echo "Virtualenv: $VENV_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

# Create or reuse the virtual environment.
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
VENV_PY="$VENV_DIR/bin/python"

# Install Python dependencies.
echo "Installing dependencies..."
"$VENV_PY" -m pip install --upgrade pip -q
"$VENV_PY" -m pip install -r "$REPO_DIR/requirements.txt" -q
"$VENV_PY" -m pip install msal requests -q

# Ensure automation script is executable.
chmod +x "$REPO_DIR/run_automation.sh"

# Create log directory.
mkdir -p "$LOG_DIR"

build_launch_agent_plist() {
  mkdir -p "$LOG_DIR"
  cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.mail_automation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$REPO_DIR/run_automation.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd.stderr.log</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF
}

# Quick env reminder.
if [ ! -f "$HOME/.config/op/mail_automation.env.op.sh" ]; then
  echo "WARNING: Env file not found at ~/.config/op/mail_automation.env.op.sh" >&2
fi

# Install and load the launchd job only when explicitly requested. The primary
# local path is on-demand because this machine's global agent policy forbids
# LaunchAgents after repeated freeze incidents.
if [ "$INSTALL_LAUNCH_AGENT" = "1" ]; then
  mkdir -p "$(dirname "$PLIST_DEST")"
  build_launch_agent_plist

  AGENT_ID="gui/$(id -u)"
  LABEL="com.user.mail_automation"

  # Unload old job if exists
  launchctl bootout "$AGENT_ID/$LABEL" 2>/dev/null || true

  # Also unload the old gmail_labeler job
  launchctl bootout "$AGENT_ID/com.user.gmail_labeler" 2>/dev/null || true

  # Load new job
  launchctl bootstrap "$AGENT_ID" "$PLIST_DEST"

  echo "LaunchAgent installed: $PLIST_DEST"
  echo "Scheduled to run daily at 9:00 AM"
else
  echo "LaunchAgent install skipped. Use scripts/intake_now.sh for on-demand intake."
  echo "To opt into launchd on a machine where it is allowed: INSTALL_LAUNCH_AGENT=1 ./deploy.sh"
fi

echo ""
echo "Deployment complete!"
echo ""
echo "Commands:"
echo "  Intake now:  $REPO_DIR/scripts/intake_now.sh"
echo "  Run now:     $REPO_DIR/run_automation.sh"
echo "  Check logs:  tail -f $LOG_DIR/launchd.stdout.log"
echo "  Status:      launchctl list | grep mail_automation"
echo "  Unload:      launchctl bootout gui/\$(id -u)/com.user.mail_automation"
