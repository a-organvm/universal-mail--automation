-- route_bulk_senders.applescript — move newsletter/bulk senders to a folder,
-- but NEVER move a protected sender (legal / bank / government) out of the inbox,
-- even if it happens to match a bulk domain.
--
-- The protected-sender decision is delegated to the project's CANONICAL gate
-- (core/rules.py is_protected_sender) via tools/protected_senders_filter.py. It
-- FAILS CLOSED: if the gate cannot be reached, the message is treated as protected
-- and left in the inbox.

-- Edit this list based on your report
set bulkDomains to {"mailchimp.com", "substack.com", "newsletter.yourfav.com"}
set bulkMailboxName to "Newsletters" -- create this mailbox in Mail first
set bulkAccountName to "" -- e.g. "iCloud" if needed

-- REQUIRED: absolute path to your universal-mail--automation checkout (the gate lives there).
-- Leave "" and the script will refuse to move anything (preflight aborts).
set repoPath to "" -- e.g. "/Users/you/Code/universal-mail--automation"
set pythonBin to "python3" -- or (repoPath & "/.venv/bin/python3")

-- Confirm the gate is reachable and correct BEFORE touching any mail.
my preflight_gate(repoPath, pythonBin)

on is_bulk_sender(theSender, domainList)
    repeat with d in domainList
        set dom to contents of d
        if theSender contains ("@" & dom) or theSender ends with dom then
            return true
        end if
    end repeat
    return false
end is_bulk_sender

tell application "Mail"
    if bulkAccountName is "" then
        set bulkMailbox to mailbox bulkMailboxName
    else
        set bulkMailbox to mailbox bulkMailboxName of account bulkAccountName
    end if

    set inboxMessages to messages of inbox
    repeat with msg in inboxMessages
        try
            set s to (sender of msg) as string
            if (my is_bulk_sender(s, bulkDomains)) and not (my is_protected(s, repoPath, pythonBin)) then
                move msg to bulkMailbox
            end if
        end try
    end repeat
end tell

-- True if this sender must NEVER be moved. FAILS CLOSED: any error (gate
-- unreachable, bad config) returns true so the message stays in the inbox.
on is_protected(theSender, repoPath, pythonBin)
    if repoPath is "" then return true
    try
        set helperPath to repoPath & "/tools/protected_senders_filter.py"
        set cmd to quoted form of pythonBin & space & quoted form of helperPath & " --one " & quoted form of theSender
        set verdict to do shell script cmd
        return (verdict is not "OK")
    on error
        return true -- fail closed: gate unavailable -> never move
    end try
end is_protected

-- Probe the gate with a known-protected and known-unprotected address; abort the
-- whole run on any mismatch so we never move mail without a working gate.
on preflight_gate(repoPath, pythonBin)
    if repoPath is "" then error "route_bulk_senders: repoPath is not set — refusing to move mail without the protected-sender gate. Edit repoPath at the top of this script."
    if (my is_protected("probe@irs.gov", repoPath, pythonBin)) is false then error "route_bulk_senders: protected-sender gate FAILED preflight (a known-protected probe was not protected). Refusing to move. Check repoPath / pythonBin."
    if (my is_protected("probe@definitely-not-protected.example", repoPath, pythonBin)) is true then error "route_bulk_senders: protected-sender gate FAILED preflight (a known-unprotected probe was protected — the gate is likely erroring and failing closed). Refusing to move. Check repoPath / pythonBin."
end preflight_gate
