-- archive_old_inbox.applescript — archive inbox mail older than a threshold,
-- but NEVER move a protected sender (legal / bank / government) out of the inbox.
--
-- The protected-sender decision is delegated to the project's CANONICAL gate
-- (core/rules.py is_protected_sender) via tools/protected_senders_filter.py, so
-- this script enforces the SAME guarantee as the Python engine instead of
-- duplicating the rule set. It FAILS CLOSED: if the gate cannot be reached
-- (repoPath unset, Python missing, any error) the message is treated as protected
-- and left in the inbox — a broken gate can never cause data-loss, it can only
-- decline to archive.

set days_threshold to 90
set cutoffDate to (current date) - (days_threshold * days)

set targetMailboxName to "Archive" -- change to your desired mailbox name
set targetAccountName to "" -- optional: e.g. "iCloud"; "" to use the default account

-- REQUIRED: absolute path to your universal-mail--automation checkout (the gate lives there).
-- Leave "" and the script will refuse to archive (preflight aborts).
set repoPath to "" -- e.g. "/Users/you/Code/universal-mail--automation"
-- Python that can import the repo. "python3" is fine for the gate, or point at the
-- venv created by deploy.sh, e.g. (repoPath & "/.venv/bin/python3").
set pythonBin to "python3"

-- Confirm the gate is reachable and correct BEFORE touching any mail. Aborts loudly
-- (archiving nothing) on misconfiguration instead of silently doing nothing.
my preflight_gate(repoPath, pythonBin)

tell application "Mail"
    set inboxMessages to messages of inbox
    if targetAccountName is "" then
        set targetMailbox to mailbox targetMailboxName
    else
        set targetMailbox to mailbox targetMailboxName of account targetAccountName
    end if

    repeat with msg in inboxMessages
        try
            if date received of msg < cutoffDate then
                set theSender to (sender of msg) as string
                if not (my is_protected(theSender, repoPath, pythonBin)) then
                    move msg to targetMailbox
                end if
            end if
        end try
    end repeat
end tell

-- True if this sender must NEVER be archived. FAILS CLOSED: any error (gate
-- unreachable, bad config) returns true so the message stays in the inbox.
on is_protected(theSender, repoPath, pythonBin)
    if repoPath is "" then return true
    try
        set helperPath to repoPath & "/tools/protected_senders_filter.py"
        set cmd to quoted form of pythonBin & space & quoted form of helperPath & " --one " & quoted form of theSender
        set verdict to do shell script cmd
        return (verdict is not "OK")
    on error
        return true -- fail closed: gate unavailable -> never archive
    end try
end is_protected

-- Probe the gate with a known-protected and known-unprotected address; abort the
-- whole run on any mismatch so we never archive without a working gate.
on preflight_gate(repoPath, pythonBin)
    if repoPath is "" then error "archive_old_inbox: repoPath is not set — refusing to archive without the protected-sender gate. Edit repoPath at the top of this script."
    if (my is_protected("probe@irs.gov", repoPath, pythonBin)) is false then error "archive_old_inbox: protected-sender gate FAILED preflight (a known-protected probe was not protected). Refusing to archive. Check repoPath / pythonBin."
    if (my is_protected("probe@definitely-not-protected.example", repoPath, pythonBin)) is true then error "archive_old_inbox: protected-sender gate FAILED preflight (a known-unprotected probe was protected — the gate is likely erroring and failing closed). Refusing to archive. Check repoPath / pythonBin."
end preflight_gate
