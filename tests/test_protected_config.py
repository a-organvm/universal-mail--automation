"""core/rules._load_local_protected must honor its 'Never raises' contract even
when the gitignored local protected-senders config contains non-UTF-8 bytes.

Review U067: a single 0xff byte in the local config raised UnicodeDecodeError at
module import time (the open used encoding='utf-8' and only caught
FileNotFoundError/OSError), which crashed `import core.rules` and disabled the
ENTIRE protected-sender gate. The fix reads with errors='replace' and never lets
a malformed config crash the import.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_import_survives_non_utf8_config_and_recovers_clean_lines(tmp_path):
    cfg = tmp_path / "protected_senders.local.txt"
    # A real protected domain, a line with invalid UTF-8 bytes, then another real
    # domain + a self mailbox. The bad bytes must not nuke the clean entries.
    cfg.write_bytes(
        b"good-lawfirm.com\n"
        b"\xff\xfe\x00 garbage-bytes-line\n"
        b"alerts.example-bank.com\n"
        b"self: me@example.com\n"
    )
    env = {**os.environ, "PROTECTED_SENDERS_FILE": str(cfg)}
    r = subprocess.run(
        [sys.executable, "-c",
         "import core.rules as r;"
         "assert r.is_protected_sender('a@good-lawfirm.com'), 'lawfirm domain lost';"
         "assert r.is_protected_sender('a@alerts.example-bank.com'), 'bank domain lost';"
         "assert r.is_protected_sender('a@irs.gov'), 'example default lost';"
         "print('ok')"],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"import crashed on non-utf8 config:\n{r.stderr}"
    assert "ok" in r.stdout


def test_load_local_protected_does_not_raise_on_bad_bytes(tmp_path, monkeypatch):
    cfg = tmp_path / "p.txt"
    cfg.write_bytes(b"\xff\xfe\x00not-utf8\nexample-lawfirm.com\nself: you@x.com\n")
    monkeypatch.setenv("PROTECTED_SENDERS_FILE", str(cfg))
    from core.rules import _load_local_protected
    domains, selfs = _load_local_protected()  # must NOT raise
    assert "example-lawfirm.com" in domains
    assert "you" in selfs


def test_missing_config_still_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTECTED_SENDERS_FILE", str(tmp_path / "does-not-exist.txt"))
    from core.rules import _load_local_protected
    domains, selfs = _load_local_protected()
    assert domains == [] and selfs == set()
