"""
Gmail Archive Labeling Automation
Author: Comprehensive Email Organization System
Purpose: Exhaustively label all emails in Gmail with semantic categories

LEGACY/STANDALONE — relabel-only; does NOT remove INBOX and does NOT enforce the
protected-sender gate (core.rules.is_protected_sender). Superseded by cli.py /
gmail_labeler.py. Do NOT extend it to archive or move out of inbox without
adopting that gate first.
"""

import time
import socket
from collections import OrderedDict
from collections import defaultdict
from datetime import datetime
import importlib.metadata as importlib_metadata

# Ensure packages_distributions is available on Python <3.10
if not hasattr(importlib_metadata, "packages_distributions"):
    try:
        import importlib_metadata as backport

        importlib_metadata.packages_distributions = backport.packages_distributions  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

from googleapiclient.errors import HttpError

import gmail_auth
from core.rules import LABEL_RULES as CORE_LABEL_RULES, categorize_from_strings

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# LABEL TAXONOMY - Compatibility projection over core.rules

_LEGACY_CATCH_ALL = "Uncategorized"


def _build_legacy_rules():
    projected = OrderedDict()
    for name, config in CORE_LABEL_RULES.items():
        if name == "Misc/Other":
            projected[_LEGACY_CATCH_ALL] = dict(config)
        else:
            projected[name] = dict(config)

    if _LEGACY_CATCH_ALL not in projected:
        projected[_LEGACY_CATCH_ALL] = {"patterns": [r".*"], "priority": 999}

    return projected


LABEL_RULES = _build_legacy_rules()


def _normalize_legacy_label(label_name):
    """Translate core taxonomy names back to legacy-compatible naming."""
    return _LEGACY_CATCH_ALL if label_name == "Misc/Other" else label_name



# ============================================================================
# AUTHENTICATION
# ============================================================================

def get_gmail_service():
    """Authenticate and return Gmail API service."""
    return gmail_auth.build_gmail_service(scopes=SCOPES)


# ============================================================================
# LABEL MANAGEMENT
# ============================================================================

def execute_with_retry(request, retries=4, base_sleep=1.0):
    """Execute a Google API request with simple exponential backoff."""
    for attempt in range(retries):
        try:
            return request.execute()
        except (HttpError, OSError, socket.error) as exc:  # noqa: B902
            if attempt == retries - 1:
                raise
            delay = base_sleep * (2 ** attempt)
            print(f"  ✗ Retryable error ({exc}); retrying in {delay:.1f}s...")
            time.sleep(delay)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            delay = base_sleep * (2 ** attempt)
            print(f"  ✗ Retryable error ({exc}); retrying in {delay:.1f}s...")
            time.sleep(delay)


def get_or_create_label(service, label_name):
    """Get label ID, create if it doesn't exist."""
    try:
        results = execute_with_retry(service.users().labels().list(userId="me"))
        labels = results.get("labels", [])
        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        label_object = {"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        created_label = execute_with_retry(service.users().labels().create(userId="me", body=label_object))
        print(f"✓ Created label: {label_name}")
        return created_label["id"]
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Error with label {label_name}: {exc}")
        return None


# ============================================================================
# EMAIL CATEGORIZATION
# ============================================================================

def categorize_email(email_data):
    """Determine best label for an email based on sender/subject."""
    headers = email_data.get("payload", {}).get("headers", [])
    sender = ""
    subject = ""
    for header in headers:
        name = header.get("name", "").lower()
        if name == "from":
            sender = header.get("value", "")
        elif name == "subject":
            subject = header.get("value", "")

    return _normalize_legacy_label(categorize_from_strings(sender, subject))


# ============================================================================
# BULK LABELING ENGINE
# ============================================================================

def label_all_unlabeled_emails(service, batch_size=500, max_emails=None, query="has:nouserlabels"):
    """
    Exhaustively label emails matching the query (default: no user labels).

    Args:
        service: Gmail API service.
        batch_size: Number of emails to process per batch (max 500).
        max_emails: Maximum total emails to process (None = all).
        query: Gmail search query to select messages (defaults to has:nouserlabels).
    """
    label_id_cache = {}
    for label_name in LABEL_RULES.keys():
        label_id = get_or_create_label(service, label_name)
        if label_id:
            label_id_cache[label_name] = label_id
    uncategorized_id = label_id_cache.get("Uncategorized")

    print(f"\n{'='*70}")
    print("Gmail Archive Exhaustive Labeling - Started")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Query: {query}")
    print(f"{'='*70}\n")

    stats = defaultdict(int)
    total_processed = 0
    page_token = None

    try:
        while True:
            results = execute_with_retry(
                service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=min(batch_size, 500),
                    pageToken=page_token,
                )
            )
            messages = results.get("messages", [])
            if not messages:
                print("\n✓ No more unlabeled emails found!")
                break

            print(f"\n📧 Processing batch of {len(messages)} emails...")

            for idx, message in enumerate(messages, 1):
                try:
                    email_data = execute_with_retry(
                        service.users().messages().get(
                            userId="me",
                            id=message["id"],
                            format="metadata",
                            metadataHeaders=["From", "Subject"],
                        )
                    )

                    label_name = categorize_email(email_data)
                    label_id = label_id_cache.get(label_name)
                    if label_id:
                        body = {"addLabelIds": [label_id]}
                        if uncategorized_id and label_name != "Uncategorized":
                            body["removeLabelIds"] = [uncategorized_id]
                        execute_with_retry(service.users().messages().modify(userId="me", id=message["id"], body=body))

                        stats[label_name] += 1
                        total_processed += 1
                        if idx % 50 == 0:
                            print(f"  ⚡ Processed {idx}/{len(messages)} in batch...")

                    if idx % 100 == 0:
                        time.sleep(1)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ✗ Error processing email {message['id']}: {exc}")
                    continue

            if max_emails and total_processed >= max_emails:
                print(f"\n⚠️  Reached maximum of {max_emails} emails")
                break

            page_token = results.get("nextPageToken")
            if not page_token:
                break

            print(f"\n📊 Progress: {total_processed} emails labeled so far")
            print("Current distribution:")
            for label, count in sorted(stats.items(), key=lambda item: item[1], reverse=True)[:5]:
                print(f"  • {label}: {count}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
    except Exception as exc:  # noqa: BLE001
        print(f"\n✗ Fatal error: {exc}")
    finally:
        print(f"\n{'='*70}")
        print("FINAL STATISTICS")
        print(f"{'='*70}")
        print(f"Total emails processed: {total_processed:,}")
        print("\nLabel distribution:")
        for label, count in sorted(stats.items(), key=lambda item: item[1], reverse=True):
            percentage = (count / total_processed * 100) if total_processed else 0
            print(f"  {label:30} {count:6,} ({percentage:5.1f}%)")
        print(f"\n{'='*70}")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        return stats


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_labeling_complete(service):
    """Check how many unlabeled emails remain."""
    try:
        results = service.users().messages().list(userId="me", q="has:nouserlabels", maxResults=1).execute()
        remaining = results.get("resultSizeEstimate", 0)
        if remaining == 0:
            print("\n✓✓✓ SUCCESS: All emails are now labeled! ✓✓✓")
            return True

        print(f"\n⚠️  {remaining:,} unlabeled emails still remain")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Error checking status: {exc}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    import warnings

    warnings.warn(
        "gmail_labeler_legacy.py is DEPRECATED: it does not enforce the "
        "protected-sender gate (core.rules.is_protected_sender). "
        "Use `python3 cli.py label --provider gmail` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    print("=" * 70)
    print(" Gmail Archive Exhaustive Labeling System")
    print(" ⚠️  DEPRECATED — use `python3 cli.py label --provider gmail` instead.")
    print("     This script lacks the protected-sender gate and relabel-only")
    print("     safety checks enforced by the unified CLI.")
    print("=" * 70)

    print("\n🔐 Authenticating with Gmail API...")
    service = get_gmail_service()
    print("✓ Authentication successful!")

    print("\n🚀 Starting exhaustive labeling process...")
    print("   This will process ALL unlabeled emails in your archive")
    print("   Press Ctrl+C at any time to pause\n")

    label_all_unlabeled_emails(service, batch_size=500, max_emails=None)

    print("\n🔍 Verifying labeling completeness...")
    verify_labeling_complete(service)

    print("\n✓ Labeling run complete.")


if __name__ == "__main__":
    main()
