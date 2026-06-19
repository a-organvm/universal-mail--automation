# Installation

Universal Mail Automation ships three ways: a **PyPI wheel** (the unified
`umail` CLI), an **editable source checkout** for development, and a
self-contained **macOS bundle** with a LaunchAgent for daily scheduling.

- Package name on PyPI: **`universal-mail-automation`**
- Console commands: **`umail`** (unified CLI) and **`umail-mcp`** (MCP server)
- Python: **3.9+** for the core/Gmail engine (the `mcp` extra requires 3.10+)

---

## 1. Install from PyPI (recommended)

```bash
# Default install — Gmail provider only
pip install universal-mail-automation

umail --version
umail health --provider gmail
```

### Optional extras

The base install is intentionally lean (Gmail only). Pull in other providers
and surfaces as extras:

| Extra      | Adds                                   | Install                                          |
|------------|----------------------------------------|--------------------------------------------------|
| `outlook`  | Outlook.com / Microsoft Graph          | `pip install "universal-mail-automation[outlook]"` |
| `yaml`     | `config.yaml` support                  | `pip install "universal-mail-automation[yaml]"`    |
| `api`      | FastAPI HTTP surface + Stripe billing  | `pip install "universal-mail-automation[api]"`     |
| `mcp`      | MCP server (`umail-mcp`, Python 3.10+) | `pip install "universal-mail-automation[mcp]"`     |
| `all`      | everything except `mcp`                | `pip install "universal-mail-automation[all]"`     |

```bash
# Example: Gmail + Outlook + YAML config
pip install "universal-mail-automation[outlook,yaml]"
```

> Using a virtualenv is recommended to isolate dependencies:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install universal-mail-automation
> ```

---

## 2. Install from source

```bash
git clone https://github.com/organvm-iii-ergon/universal-mail--automation.git
cd universal-mail--automation

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"      # editable install with all extras + dev tools

# Run the test suite (offline, no accounts needed)
pytest -q
```

The legacy `./deploy.sh` flow (venv + `requirements.txt` + launchd job) still
works unchanged for existing setups.

### Build the distributions yourself

```bash
pip install build twine
python -m build              # → dist/*.whl and dist/*.tar.gz
twine check dist/*           # validate metadata
```

---

## 3. macOS bundle

The bundle is a relocatable directory containing a private virtualenv with the
package pre-installed (`outlook` + `yaml` extras), a `bin/umail` launcher that
works without activating anything, and a LaunchAgent for daily runs.

### Build it

```bash
# From a source checkout (builds a wheel, then bundles it):
scripts/build_macos_bundle.sh

# …or from an already-built wheel:
scripts/build_macos_bundle.sh dist/universal_mail_automation-0.2.0-py3-none-any.whl
```

This produces `dist/universal-mail-automation-<version>-macos.tar.gz`.

### Install it

```bash
tar -xzf universal-mail-automation-0.2.0-macos.tar.gz
cd universal-mail-automation-0.2.0-macos

# Run the CLI directly — no activation needed:
./bin/umail --help

# (Optional) install the daily 9 AM Gmail labeling LaunchAgent:
./install.sh
```

`install.sh` patches the bundle's absolute path into the LaunchAgent plist,
copies it to `~/Library/LaunchAgents/com.user.mail_automation.plist`, and loads
it with `launchctl`. Check status with:

```bash
launchctl list | grep com.user.mail_automation
```

To uninstall the schedule:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.mail_automation.plist
rm ~/Library/LaunchAgents/com.user.mail_automation.plist
```

---

## Configuration & credentials

Installation only puts the code in place. To actually process mail you still
need provider credentials — see the
[Configuration](README.md#configuration) section of the README for Gmail OAuth
(1Password-backed), IMAP app passwords, Outlook Azure app registration, and the
optional `~/.config/mail_automation/config.yaml` file.

---

## Publishing (maintainers)

Releases are automated by `.github/workflows/publish.yml`:

1. Bump `__version__` in `core/__init__.py` and update `CHANGELOG.md`.
2. Tag and push: `git tag v0.2.0 && git push origin v0.2.0`.
3. The workflow builds the sdist + wheel, builds the macOS bundle, and — on a
   published GitHub Release — uploads to PyPI via Trusted Publishing (OIDC) and
   attaches the macOS bundle to the release.

PyPI Trusted Publishing must be configured once for this repo/workflow under
the project's publishing settings; no long-lived API token is stored.
