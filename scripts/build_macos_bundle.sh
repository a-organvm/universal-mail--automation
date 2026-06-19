#!/usr/bin/env bash
#
# Build a self-contained macOS bundle for Universal Mail Automation.
#
# The bundle is a relocatable directory containing a private virtualenv with the
# package (and the `outlook` + `yaml` extras) installed, a `bin/umail` launcher
# that works without activating the venv, and a LaunchAgent plist template for
# scheduling. It is emitted as a versioned `.tar.gz` under `dist/`.
#
# Usage:
#   scripts/build_macos_bundle.sh            # build wheel from source, then bundle
#   scripts/build_macos_bundle.sh dist/universal_mail_automation-0.2.0-py3-none-any.whl
#
# Requirements: macOS, python3 (>=3.9). Run from the repository root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
DIST_DIR="$REPO_ROOT/dist"
mkdir -p "$DIST_DIR"

# 1. Resolve a wheel to install — either the one passed in, or build a fresh one.
WHEEL="${1:-}"
if [[ -z "$WHEEL" ]]; then
    echo "==> Building wheel from source"
    "$PYTHON" -m pip install --quiet --upgrade build
    "$PYTHON" -m build --wheel --outdir "$DIST_DIR"
    WHEEL="$(ls -t "$DIST_DIR"/*.whl | head -n1)"
fi
if [[ ! -f "$WHEEL" ]]; then
    echo "error: wheel not found: $WHEEL" >&2
    exit 1
fi
echo "==> Using wheel: $WHEEL"

# Derive version from core/__init__.py so the artifact name matches the package.
VERSION="$("$PYTHON" -c 'import re,pathlib; print(re.search(r"__version__ = \"([^\"]+)\"", pathlib.Path("core/__init__.py").read_text()).group(1))')"
BUNDLE_NAME="universal-mail-automation-${VERSION}-macos"
STAGE="$(mktemp -d)/${BUNDLE_NAME}"
trap 'rm -rf "$(dirname "$STAGE")"' EXIT
mkdir -p "$STAGE"

# 2. Build a private virtualenv inside the bundle and install the wheel + extras.
echo "==> Creating bundled virtualenv"
"$PYTHON" -m venv "$STAGE/venv"
"$STAGE/venv/bin/pip" install --quiet --upgrade pip
"$STAGE/venv/bin/pip" install --quiet "${WHEEL}[outlook,yaml]"

# 3. Relocatable launcher: resolve its own location, then exec the venv python.
mkdir -p "$STAGE/bin"
cat > "$STAGE/bin/umail" <<'LAUNCHER'
#!/usr/bin/env bash
# Relocatable launcher for the bundled Universal Mail Automation CLI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/../venv/bin/umail" "$@"
LAUNCHER
chmod +x "$STAGE/bin/umail"

# 4. LaunchAgent template for daily scheduling (paths patched at install time).
mkdir -p "$STAGE/LaunchAgents"
cat > "$STAGE/LaunchAgents/com.user.mail_automation.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.mail_automation</string>
    <key>ProgramArguments</key>
    <array>
        <string>__BUNDLE_DIR__/bin/umail</string>
        <string>label</string>
        <string>--provider</string>
        <string>gmail</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>__BUNDLE_DIR__/mail_automation.log</string>
    <key>StandardErrorPath</key>
    <string>__BUNDLE_DIR__/mail_automation.err.log</string>
</dict>
</plist>
PLIST

# 5. Install helper: patch the launcher path into the plist and load it.
cat > "$STAGE/install.sh" <<'INSTALL'
#!/usr/bin/env bash
# Install the bundled LaunchAgent (daily 9 AM Gmail labeling).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/Library/LaunchAgents/com.user.mail_automation.plist"
sed "s#__BUNDLE_DIR__#$HERE#g" "$HERE/LaunchAgents/com.user.mail_automation.plist" > "$DEST"
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"
echo "Installed and loaded LaunchAgent: $DEST"
echo "Run the CLI directly with: $HERE/bin/umail --help"
INSTALL
chmod +x "$STAGE/install.sh"

cp "$REPO_ROOT/README.md" "$STAGE/README.md"
cp "$REPO_ROOT/LICENSE" "$STAGE/LICENSE"
[[ -f "$REPO_ROOT/INSTALL.md" ]] && cp "$REPO_ROOT/INSTALL.md" "$STAGE/INSTALL.md"

# 6. Pack the bundle.
TARBALL="$DIST_DIR/${BUNDLE_NAME}.tar.gz"
echo "==> Packing $TARBALL"
tar -C "$(dirname "$STAGE")" -czf "$TARBALL" "$BUNDLE_NAME"

echo "==> Done: $TARBALL"
