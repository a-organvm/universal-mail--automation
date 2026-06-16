"""Read-only historical mail export normalization.

This module creates the private raw-ish input that
``core.historical_intelligence`` consumes. It is intentionally not a dashboard
payload: exports can contain message subjects, snippets, and bounded bodies.
The safe surface is the receipt returned by ``write_mail_history_export``.
"""

from __future__ import annotations

import hashlib
import json
import mailbox
from collections.abc import Iterable as IterableABC
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

MAIL_HISTORY_EXPORT_SCHEMA = "uma.mail.history_export.v1"
MAIL_HISTORY_EXPORT_RECEIPT_SCHEMA = "uma.mail.history_export.receipt.v1"

DEFAULT_BODY_CHAR_LIMIT = 4000
DEFAULT_SNIPPET_CHAR_LIMIT = 280

_JSON_SUFFIXES = {".json"}
_JSONL_SUFFIXES = {".jsonl", ".ndjson"}
_EML_SUFFIXES = {".eml", ".emlx"}
_MBOX_SUFFIXES = {".mbox", ".mbx"}
_PRIVATE_SOURCE_FIELDS = ["full_source_path", "attachments", "raw_headers"]


class MailHistoryExportError(ValueError):
    """Raised when a historical mail source cannot be exported safely."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:
            raw = raw / 1000
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace(" ", "T", 1)):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _coerce_window(value: Optional[str], label: str) -> Optional[datetime]:
    if value is None:
        return None
    parsed = _parse_dt(value)
    if parsed is None:
        raise MailHistoryExportError(f"{label} must be a parseable date or timestamp")
    return parsed


def _within_window(received_at: Optional[datetime], since: Optional[datetime], until: Optional[datetime]) -> bool:
    if received_at is None:
        return True
    if since and received_at < since:
        return False
    if until and received_at >= until:
        return False
    return True


def _first_string(row: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        return [value.strip()]
    if isinstance(value, IterableABC) and not isinstance(value, (bytes, bytearray, dict)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _scope_from_path(path: Path, mailbox_hint: Optional[str]) -> str:
    if mailbox_hint:
        return mailbox_hint
    names = [part.lower() for part in path.parts]
    joined = "/".join(names)
    if "sent" in joined:
        return "Sent"
    if "draft" in joined:
        return "Drafts"
    if "junk" in joined or "spam" in joined:
        return "Junk"
    if "trash" in joined or "deleted" in joined:
        return "Trash"
    if "archive" in joined or "[gmail]/all mail" in joined or "all mail" in joined:
        return "Archive"
    if "inbox" in joined:
        return "Inbox"
    return "Unknown"


def _scope_from_row(row: Dict[str, Any], fallback: str) -> str:
    return _first_string(row, "scope", "mailbox", "folder", "label_scope") or fallback


def _state_from_row(row: Dict[str, Any]) -> str:
    raw = _first_string(row, "state", "read_state", "status")
    if raw:
        lowered = raw.lower()
        if lowered in {"read", "seen"}:
            return "read"
        if lowered in {"unread", "unseen"}:
            return "unread"
        return raw
    labels = " ".join(label.lower() for label in _listify(row.get("labels") or row.get("labelIds")))
    if "unread" in labels:
        return "unread"
    return "unknown"


def _direction_from_row(row: Dict[str, Any], scope: str, self_addresses: Iterable[str]) -> str:
    raw = _first_string(row, "direction")
    if raw:
        lowered = raw.lower()
        if lowered in {"sent", "out", "outbound", "from_me", "me"}:
            return "outbound"
        if lowered in {"in", "inbound", "received"}:
            return "inbound"
    if scope.lower() in {"sent", "sent mail"}:
        return "outbound"
    sender = (_first_string(row, "address", "from_address", "sender_email") or "").lower()
    if sender and sender in {addr.lower() for addr in self_addresses}:
        return "outbound"
    return "inbound"


def _snippet(text: Optional[str], limit: int = DEFAULT_SNIPPET_CHAR_LIMIT) -> Optional[str]:
    if not isinstance(text, str):
        return None
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    return cleaned[:limit]


def _body_text(msg: Message, limit: int) -> Optional[str]:
    parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                text = part.get_content()
            except (LookupError, UnicodeDecodeError, AttributeError):
                continue
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    else:
        if msg.get_content_type() == "text/plain":
            try:
                text = msg.get_content()
            except (LookupError, UnicodeDecodeError, AttributeError):
                text = None
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    if not parts:
        return None
    return "\n\n".join(parts)[:limit]


def _address_pair(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(raw, str):
        return None, None
    name, address = parseaddr(raw)
    return (name or None), (address.lower() or None)


def _message_to_record(
    msg: Message,
    *,
    source_key: str,
    source_name: str,
    scope: str,
    self_addresses: Iterable[str],
    body_char_limit: int,
) -> Dict[str, Any]:
    sender_name, sender_address = _address_pair(str(msg.get("From") or ""))
    received_at = _parse_dt(msg.get("Date"))
    labels = _listify(msg.get("X-Gmail-Labels")) + _listify(msg.get("Keywords"))
    message_id = str(msg.get("Message-ID") or "").strip(" <>") or None
    in_reply_to = str(msg.get("In-Reply-To") or "").strip(" <>") or None
    references = _listify(msg.get("References"))
    thread_id = in_reply_to or (references[-1].strip(" <>") if references else None) or message_id
    subject = str(msg.get("Subject") or "").strip() or None
    body = _body_text(msg, body_char_limit)
    row = {
        "source_ref": _hash("source", source_key),
        "source_name": source_name,
        "message_id": message_id or _hash("msgid", source_key),
        "thread_id": thread_id or _hash("thread", source_key, subject),
        "received_at": _format_dt(received_at),
        "direction": "outbound" if sender_address and sender_address in {addr.lower() for addr in self_addresses} else "inbound",
        "scope": scope,
        "state": "unknown",
        "labels": sorted(set(labels + ([scope] if scope != "Unknown" else []))),
        "sender": sender_name,
        "address": sender_address,
        "subject": subject,
        "snippet": _snippet(body or subject),
        "body": body,
    }
    if scope.lower() in {"sent", "sent mail"}:
        row["direction"] = "outbound"
    row["id"] = _hash("hist", row["message_id"], row["received_at"], row["source_ref"])
    return row


def _normalize_row(
    row: Dict[str, Any],
    *,
    source_key: str,
    source_name: str,
    fallback_scope: str,
    self_addresses: Iterable[str],
    body_char_limit: int,
) -> Dict[str, Any]:
    scope = _scope_from_row(row, fallback_scope)
    body = _first_string(row, "body", "text", "content")
    if isinstance(body, str):
        body = body[:body_char_limit]
    subject = _first_string(row, "subject", "title")
    sender = _first_string(row, "sender", "from", "from_name")
    address = _first_string(row, "address", "from_address", "sender_email")
    if not address and sender:
        parsed_name, parsed_addr = _address_pair(sender)
        sender = parsed_name or sender
        address = parsed_addr
    received_at = _parse_dt(
        row.get("received_at")
        or row.get("received")
        or row.get("date")
        or row.get("internalDate")
        or row.get("timestamp")
    )
    labels = _listify(row.get("labels") or row.get("labelIds") or row.get("mail_triage_labels"))
    if scope != "Unknown":
        labels.append(scope)
    out = {
        "source_ref": _hash("source", source_key, row.get("id") or row.get("message_id")),
        "source_name": source_name,
        "message_id": str(row.get("message_id") or row.get("id") or row.get("rowid") or _hash("msgid", source_key)),
        "thread_id": str(
            row.get("thread_id")
            or row.get("conversation_id")
            or row.get("thread")
            or row.get("in_reply_to")
            or row.get("message_id")
            or row.get("id")
            or _hash("thread", source_key, subject)
        ),
        "received_at": _format_dt(received_at),
        "direction": _direction_from_row(row, scope, self_addresses),
        "scope": scope,
        "state": _state_from_row(row),
        "labels": sorted(set(labels)),
        "sender": sender,
        "address": address.lower() if isinstance(address, str) else address,
        "subject": subject,
        "snippet": _first_string(row, "snippet", "summary") or _snippet(body or subject),
        "body": body,
    }
    out["id"] = _hash("hist", out["message_id"], out["received_at"], out["source_ref"])
    return out


def _read_json_rows(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailHistoryExportError("mail history JSON source is invalid") from e
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)], {}
    if not isinstance(data, dict):
        raise MailHistoryExportError("mail history JSON source must be an object or array")
    rows = data.get("messages")
    if rows is None:
        rows = data.get("records")
    if rows is None:
        rows = data.get("items")
    if not isinstance(rows, list):
        raise MailHistoryExportError("mail history JSON source requires messages, records, or items")
    return [row for row in rows if isinstance(row, dict)], data


def _read_jsonl_rows(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise MailHistoryExportError(f"mail history JSONL source is invalid at line {line_number}") from e
            if isinstance(row, dict):
                rows.append(row)
    except OSError as e:
        raise MailHistoryExportError(f"mail history source could not be read: {e}") from e
    return rows, {}


def _parse_email_bytes(raw: bytes) -> Message:
    return BytesParser(policy=policy.default).parsebytes(raw)


def _read_emlx_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    first_line, sep, rest = raw.partition(b"\n")
    if sep and first_line.strip().isdigit():
        size = int(first_line.strip())
        return rest[:size]
    return raw


def _iter_message_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    for suffix in ("*.emlx", "*.eml"):
        yield from sorted(path.rglob(suffix))


def _detect_source_type(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if path.is_dir():
        return "emlx_dir"
    suffix = path.suffix.lower()
    if suffix in _JSON_SUFFIXES:
        return "json"
    if suffix in _JSONL_SUFFIXES:
        return "jsonl"
    if suffix in _EML_SUFFIXES:
        return "eml"
    if suffix in _MBOX_SUFFIXES:
        return "mbox"
    return "mbox"


def _source_rows_from_path(
    path: Path,
    *,
    source_type: str,
    mailbox_hint: Optional[str],
    self_addresses: Iterable[str],
    body_char_limit: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not path.exists():
        raise MailHistoryExportError("mail history source not found", status_code=404)
    detected = _detect_source_type(path, source_type)
    source_name = path.name
    fallback_scope = _scope_from_path(path, mailbox_hint)

    if detected == "json":
        rows, metadata = _read_json_rows(path)
        return [
            _normalize_row(
                row,
                source_key=f"{source_name}:{index}",
                source_name=source_name,
                fallback_scope=fallback_scope,
                self_addresses=self_addresses,
                body_char_limit=body_char_limit,
            )
            for index, row in enumerate(rows)
        ], metadata

    if detected == "jsonl":
        rows, metadata = _read_jsonl_rows(path)
        return [
            _normalize_row(
                row,
                source_key=f"{source_name}:{index}",
                source_name=source_name,
                fallback_scope=fallback_scope,
                self_addresses=self_addresses,
                body_char_limit=body_char_limit,
            )
            for index, row in enumerate(rows)
        ], metadata

    if detected in {"eml", "emlx", "emlx_dir"}:
        out = []
        for file_path in _iter_message_files(path):
            try:
                raw = _read_emlx_bytes(file_path) if file_path.suffix.lower() == ".emlx" else file_path.read_bytes()
                msg = _parse_email_bytes(raw)
            except OSError as e:
                raise MailHistoryExportError(f"mail history source could not be read: {e}") from e
            scope = _scope_from_path(file_path, mailbox_hint)
            try:
                relative_key = str(file_path.relative_to(path))
            except ValueError:
                relative_key = file_path.name
            out.append(
                _message_to_record(
                    msg,
                    source_key=f"{source_name}:{relative_key}",
                    source_name=source_name,
                    scope=scope,
                    self_addresses=self_addresses,
                    body_char_limit=body_char_limit,
                )
            )
        return out, {}

    if detected == "mbox":
        out = []
        try:
            box = mailbox.mbox(path, create=False)
            for index, msg in enumerate(box):
                parsed = _parse_email_bytes(msg.as_bytes(policy=policy.default))
                out.append(
                    _message_to_record(
                        parsed,
                        source_key=f"{source_name}:{index}",
                        source_name=source_name,
                        scope=fallback_scope,
                        self_addresses=self_addresses,
                        body_char_limit=body_char_limit,
                    )
                )
            box.close()
        except (OSError, mailbox.Error) as e:
            raise MailHistoryExportError(f"mail history mbox source could not be read: {e}") from e
        return out, {}

    raise MailHistoryExportError(f"unsupported mail history source type: {detected}")


def _filter_rows(
    rows: List[Dict[str, Any]],
    *,
    since_dt: Optional[datetime],
    until_dt: Optional[datetime],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    filtered = []
    for row in rows:
        received_at = _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
        if not _within_window(received_at, since_dt, until_dt):
            continue
        filtered.append(row)
        if limit is not None and len(filtered) >= limit:
            break
    return filtered


def build_mail_history_export(
    source_path: Union[Path, str],
    *,
    source_type: str = "auto",
    since: Optional[str] = None,
    until_exclusive: Optional[str] = None,
    limit: Optional[int] = None,
    body_char_limit: int = DEFAULT_BODY_CHAR_LIMIT,
    self_addresses: Optional[Iterable[str]] = None,
    mailbox_hint: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a private normalized historical export from local mail sources.

    Supported sources are JSON objects/arrays, JSONL/NDJSON, mbox files, EML
    files, EMLX files, and directories containing EML/EMLX messages. The source
    is read-only. Attachments and full source paths are never copied into rows.
    """
    path = Path(source_path).expanduser()
    if limit is not None and int(limit) < 1:
        raise MailHistoryExportError("limit must be greater than zero")
    body_limit = max(0, int(body_char_limit))
    self_address_list = [addr.strip().lower() for addr in (self_addresses or []) if str(addr).strip()]
    since_dt = _coerce_window(since, "since")
    until_dt = _coerce_window(until_exclusive, "until_exclusive")
    if since_dt and until_dt and until_dt <= since_dt:
        raise MailHistoryExportError("until_exclusive must be after since")

    rows, source_metadata = _source_rows_from_path(
        path,
        source_type=source_type,
        mailbox_hint=mailbox_hint,
        self_addresses=self_address_list,
        body_char_limit=body_limit,
    )
    effective_since = since or source_metadata.get("since")
    effective_until = until_exclusive or source_metadata.get("until_exclusive")
    if effective_since != since:
        since_dt = _coerce_window(effective_since, "since")
    if effective_until != until_exclusive:
        until_dt = _coerce_window(effective_until, "until_exclusive")
    rows = _filter_rows(rows, since_dt=since_dt, until_dt=until_dt, limit=limit)
    generated_at = now or _utc_now()
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    detected = _detect_source_type(path, source_type)

    return {
        "schema": MAIL_HISTORY_EXPORT_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "attachments_exported": False,
        },
        "source": {
            "type": detected,
            "filename": path.name,
            "mailbox_hint": mailbox_hint,
            "message_count": len(rows),
        },
        "generated_at": _format_dt(generated_at),
        "since": effective_since,
        "until_exclusive": effective_until,
        "privacy": {
            "private_raw_mail": True,
            "safe_for_dashboard": False,
            "stdout_safe": False,
            "omitted_source_fields": _PRIVATE_SOURCE_FIELDS,
            "body_char_limit": body_limit,
        },
        "messages": rows,
    }


def write_mail_history_export(
    export: Dict[str, Any],
    output_path: Union[Path, str],
    *,
    pretty: bool = False,
    sort_keys: bool = False,
) -> Dict[str, Any]:
    """Write a private export and return a stdout-safe receipt."""
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(export, indent=2 if pretty else None, sort_keys=sort_keys)
    path.write_text(payload + "\n", encoding="utf-8")
    stat = path.stat()
    return {
        "schema": MAIL_HISTORY_EXPORT_RECEIPT_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only_source": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "wrote_private_export": True,
        },
        "output": {
            "filename": path.name,
            "bytes": stat.st_size,
            "message_count": len(export.get("messages") or []),
            "private_raw_mail": True,
            "safe_for_dashboard": False,
        },
        "source": export.get("source", {}),
        "privacy": {
            "receipt_redacted": True,
            "raw_mail_printed_to_stdout": False,
            "output_contains_private_mail": True,
        },
        "generated_at": export.get("generated_at"),
        "since": export.get("since"),
        "until_exclusive": export.get("until_exclusive"),
    }
