"""
Archive Sorted Mail
Purpose: Retroactively remove 'INBOX' label from emails that have been successfully categorized.
This implements "Inbox Zero" for organized mail.

SAFETY: ARCHIVE_CATEGORIES includes protected-class labels (Finance/Banking,
Tech/Security), so every candidate's From is checked against the canonical
core.rules.is_protected_sender gate and protected senders are skipped (fail
closed) BEFORE the INBOX-removing batchModify. Never archive by label alone.
"""

import logging

from googleapiclient.errors import HttpError

import gmail_auth
from core.rules import is_protected_sender

# Setup
LOG_FILE = "archive_sorted.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Categories that should be ARCHIVED (removed from Inbox)
# We assume everything else (Personal, Awaiting Reply) stays.
ARCHIVE_CATEGORIES = [
    "Finance/Banking",
    "Finance/Payments",
    "Tech/Security",
    "Work/Dev/Infrastructure",
    "Work/Dev/GitHub",
    "Work/Dev/Code-Review",
    "Work/RealEstate",
    "Shopping",
    "Travel",
    "Entertainment",
    "Education/Research",
    "Professional/Jobs",
    "Services/Domain",
    "Notification",
    "Marketing",
    "AI/Grok",
    "AI/Services",
    "AI/Data Exports",
    "Misc/Other" # Even Misc should be archived if we are done with it
]

def get_service():
    return gmail_auth.build_gmail_service()


def senders_for(service, ids):
    """Fetch {id: From} via batched metadata gets. A fetch error leaves the
    sender empty, which is_protected_sender treats as protected (fail closed)."""
    out = {}

    def cb(rid, resp, exc):
        if exc or not resp:
            out[rid] = ""  # fail closed
            return
        headers = resp.get("payload", {}).get("headers", [])
        out[rid] = next(
            (h["value"] for h in headers if h.get("name", "").lower() == "from"), ""
        )

    for i in range(0, len(ids), 50):
        batch = service.new_batch_http_request(callback=cb)
        for mid in ids[i:i + 50]:
            batch.add(
                service.users().messages().get(
                    userId="me", id=mid, format="metadata", metadataHeaders=["From"]
                ),
                request_id=mid,
            )
        batch.execute()
    return out


def archive_loop():
    service = get_service()

    for category in ARCHIVE_CATEGORIES:
        logger.info(f"--- Archiving {category} ---")

        # Query: Has label X AND is in Inbox
        query = f"label:{category} label:INBOX"

        while True:
            try:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=1000
                ).execute()

                messages = results.get('messages', [])
                if not messages:
                    logger.info(f"   {category}: Clean.")
                    break

                ids = [m['id'] for m in messages]

                # PROTECTED-SENDER GATE: never archive by label alone — verify the
                # From of every candidate and drop protected senders (fail closed).
                senders = senders_for(service, ids)
                archivable = [i for i in ids if not is_protected_sender(senders.get(i, ""))]
                skipped = len(ids) - len(archivable)
                if skipped:
                    logger.info(f"   {category}: {skipped} protected sender(s) skipped.")
                if not archivable:
                    if len(ids) < 1000:
                        break
                    continue

                body = {
                    "ids": archivable,
                    "removeLabelIds": ['INBOX']
                }

                service.users().messages().batchModify(userId='me', body=body).execute()
                logger.info(f"   Archived {len(archivable)} messages...")

                # If we processed a full page, loop again to catch more (pagination via fresh query)
                if len(ids) < 1000:
                    break
            except HttpError as e:
                logger.warning(f"API Error: {e}")
                break

if __name__ == "__main__":
    archive_loop()
