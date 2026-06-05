"""Tests for icloud_triage.archive_uid — the protected, fail-safe archive move.

Focus: review U006 (and siblings U358/U359/U799/U800/U801). The old COPY
fallback called a bare, mailbox-wide ``imap.expunge()`` which permanently
deletes EVERY \\Deleted-flagged message, not just the one being archived. The
single load-bearing invariant these tests enforce is: archive_uid must NEVER
issue a mailbox-wide EXPUNGE. The FakeIMAP below trips a flag if it ever does.
"""

import imaplib

import pytest

from icloud_triage import _supports, archive_uid, imap_quote


class FakeIMAP:
    """Records every UID command; trips ``bare_expunge_called`` on the
    mailbox-wide ``expunge()`` that must never be issued."""

    def __init__(self, capabilities=(), results=None, raise_on=()):
        # imaplib exposes capabilities as a tuple of upper-case names.
        self.capabilities = tuple(c.upper() for c in capabilities)
        self.calls = []                       # list of (CMD, *args)
        self.bare_expunge_called = False
        self._results = results or {}         # CMD -> "OK"/"NO"
        self._raise_on = {c.upper() for c in raise_on}

    def uid(self, command, *args):
        cmd = command.upper()
        self.calls.append((cmd, *args))
        if cmd in self._raise_on:
            raise imaplib.IMAP4.error(f"{cmd} not supported")
        return (self._results.get(cmd, "OK"), [None])

    def expunge(self):                         # the destructive primitive
        self.bare_expunge_called = True
        return ("OK", [b"1"])

    # convenience
    def cmds(self):
        return [c[0] for c in self.calls]


# -- the load-bearing invariant ---------------------------------------------
@pytest.mark.parametrize("caps", [
    (),                       # minimal server: neither MOVE nor UIDPLUS
    ("UIDPLUS",),             # scoped expunge available
    ("MOVE",),                # atomic move available
    ("MOVE", "UIDPLUS"),      # both
])
def test_never_calls_mailbox_wide_expunge(caps):
    imap = FakeIMAP(capabilities=caps)
    archive_uid(imap, "42", "Archive")
    assert imap.bare_expunge_called is False, (
        "archive_uid issued a mailbox-wide EXPUNGE — this destroys unrelated "
        "\\Deleted mail (review U006)")


# -- MOVE path (RFC 6851) ---------------------------------------------------
def test_move_supported_uses_atomic_move_only():
    imap = FakeIMAP(capabilities=("MOVE", "UIDPLUS"))
    assert archive_uid(imap, "7", "Archive") == "moved"
    assert imap.cmds() == ["MOVE"]            # no COPY, no STORE, no EXPUNGE


def test_move_non_ok_does_not_fall_through_to_copy():
    # A non-OK MOVE that fell through to COPY would duplicate the message (U801).
    imap = FakeIMAP(capabilities=("MOVE",), results={"MOVE": "NO"})
    assert archive_uid(imap, "7", "Archive") == "failed"
    assert imap.cmds() == ["MOVE"]            # crucially: no COPY afterwards


def test_move_raises_is_treated_as_failed_not_duplicated():
    imap = FakeIMAP(capabilities=("MOVE",), raise_on=("MOVE",))
    assert archive_uid(imap, "7", "Archive") == "failed"
    assert imap.cmds() == ["MOVE"]


# -- COPY + scoped UID EXPUNGE path (RFC 4315 / UIDPLUS) --------------------
def test_copy_then_scoped_uid_expunge_when_uidplus():
    imap = FakeIMAP(capabilities=("UIDPLUS",))
    assert archive_uid(imap, "9", "Archive") == "moved"
    assert imap.cmds() == ["COPY", "STORE", "EXPUNGE"]
    # The EXPUNGE was scoped to the uid, not mailbox-wide.
    assert ("EXPUNGE", "9") in imap.calls
    assert imap.bare_expunge_called is False


def test_copy_failure_leaves_original_untouched():
    imap = FakeIMAP(capabilities=("UIDPLUS",), results={"COPY": "NO"})
    assert archive_uid(imap, "9", "Archive") == "failed"
    assert imap.cmds() == ["COPY"]            # no STORE, no EXPUNGE after a failed copy


def test_store_failure_after_copy_is_copied_not_removed():
    # Copy made but flagging the original failed -> a duplicate, reported honestly,
    # and definitely not expunged (U358/U359).
    imap = FakeIMAP(capabilities=("UIDPLUS",), results={"STORE": "NO"})
    assert archive_uid(imap, "9", "Archive") == "copied_not_removed"
    assert imap.cmds() == ["COPY", "STORE"]   # no EXPUNGE
    assert imap.bare_expunge_called is False


def test_scoped_expunge_failure_is_copied_not_removed():
    imap = FakeIMAP(capabilities=("UIDPLUS",), results={"EXPUNGE": "NO"})
    assert archive_uid(imap, "9", "Archive") == "copied_not_removed"
    assert imap.bare_expunge_called is False


# -- minimal server: no MOVE, no UIDPLUS -> fail SAFE -----------------------
def test_no_move_no_uidplus_copies_but_refuses_to_expunge():
    imap = FakeIMAP(capabilities=())          # neither extension
    assert archive_uid(imap, "9", "Archive") == "copied_not_removed"
    # Copy + flag happen, but we DECLINE any expunge (scoped or mailbox-wide).
    assert imap.cmds() == ["COPY", "STORE"]
    assert imap.bare_expunge_called is False


# -- mailbox-name quoting / injection (U799/U800) ---------------------------
def test_imap_quote_escapes_quotes_and_backslashes():
    assert imap_quote("Archive") == '"Archive"'
    assert imap_quote('Ar"ch') == '"Ar\\"ch"'
    assert imap_quote("A\\B") == '"A\\\\B"'


def test_archive_mailbox_name_is_quoted_in_command():
    imap = FakeIMAP(capabilities=("MOVE",))
    archive_uid(imap, "7", 'Weird"Name')
    # The destination argument passed to MOVE is the escaped quoted-string.
    move = next(c for c in imap.calls if c[0] == "MOVE")
    assert move[2] == '"Weird\\"Name"'


@pytest.mark.parametrize("evil", [
    'Archive"\r\nA01 DELETE INBOX',   # CRLF command injection
    "Archive\rX",                     # bare CR
    "Archive\nX",                     # bare LF
    "Archive\x00X",                   # NUL
    "Archive\x7f",                    # DEL
])
def test_imap_quote_rejects_control_characters(evil):
    # A quoted-string cannot legally carry CR/LF/NUL; rejecting them is what
    # prevents a malicious mailbox name from injecting a forged IMAP command.
    with pytest.raises(ValueError):
        imap_quote(evil)


def test_archive_uid_refuses_crlf_name_before_touching_server():
    # archive_uid must blow up on the un-encodable name BEFORE issuing any
    # command — no partial move, no injected wire bytes.
    imap = FakeIMAP(capabilities=("MOVE", "UIDPLUS"))
    with pytest.raises(ValueError):
        archive_uid(imap, "1", "Archive\r\nA01 DELETE INBOX")
    assert imap.calls == []                   # nothing reached the wire
    assert imap.bare_expunge_called is False


# -- capability detection is exact-token, not substring ---------------------
class _Caps:
    """Stands in for a connected imaplib server with a .capabilities tuple."""
    def __init__(self, caps):
        self.capabilities = tuple(caps)


def test_uidplus_does_not_misfire_on_bare_uid_token():
    assert _supports(_Caps(("UID", "UIDONLY")), "UIDPLUS") is False
    assert _supports(_Caps(("UIDPLUS",)), "UIDPLUS") is True


def test_supports_capability_query_fallback_is_exact_token():
    # No .capabilities attribute -> _supports consults capability(); the match
    # must be per-token so 'X-REMOVE' does not satisfy a 'MOVE' query.
    class NoAttr:
        def __init__(self, line):
            self._line = line
        def capability(self):
            return ("OK", [self._line])
    assert _supports(NoAttr(b"IMAP4REV1 X-REMOVE IDLE"), "MOVE") is False
    assert _supports(NoAttr(b"IMAP4REV1 MOVE UIDPLUS"), "MOVE") is True
    assert _supports(NoAttr(b"IMAP4REV1 MOVE UIDPLUS"), "UIDPLUS") is True
