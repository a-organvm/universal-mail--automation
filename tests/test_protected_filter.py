"""Tests for tools/protected_senders_filter.py — the canonical shell surface the
AppleScript movers call to enforce the protected-sender gate (review G16)."""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "tools", "protected_senders_filter.py")


def _one(sender):
    out = subprocess.run(
        [sys.executable, HELPER, "--one", sender],
        capture_output=True, text=True, cwd="/",  # cwd-independent on purpose
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _batch(senders):
    out = subprocess.run(
        [sys.executable, HELPER],
        input="\n".join(senders) + "\n",
        capture_output=True, text=True, cwd="/",
    )
    assert out.returncode == 0, out.stderr
    return [line for line in out.stdout.splitlines() if line]


def test_one_protected():
    for s in ["Jane <jane@irs.gov>", "alerts@chase.com", "x@sub.chase.com", "a@apple.com"]:
        assert _one(s) == "PROTECTED", s


def test_one_not_protected():
    for s in ["deals@shop.example", "x@purchase.com", "x@irs.gov.attacker.com", "a@random.example"]:
        assert _one(s) == "OK", s


def test_one_fails_closed_on_empty():
    # is_protected_sender fails closed: empty / unparseable -> protected.
    assert _one("") == "PROTECTED"
    assert _one("not-an-email") == "PROTECTED"


def test_batch_echoes_only_protected_verbatim():
    senders = [
        "Jane <jane@irs.gov>",      # protected
        "deals@shop.example",       # not
        "alerts@chase.com",         # protected
        "x@purchase.com",           # not (substring spoof)
    ]
    protected = _batch(senders)
    assert protected == ["Jane <jane@irs.gov>", "alerts@chase.com"]


def test_batch_runs_cwd_independent_and_importable():
    # Smoke: the sys.path insert makes the gate importable from any cwd.
    assert _batch(["a@irs.gov"]) == ["a@irs.gov"]
    assert _batch(["a@random.example"]) == []
