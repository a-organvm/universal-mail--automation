"""Service layer — wraps the mail-automation engine behind a small, safe API.

The protected-sender GATE is the product's safety core. This layer NEVER bypasses
it: every triage runs through the engine's own gate AND an independent
:class:`AuditLog` observer, and the API asserts no-violations at the boundary
*before* returning success. A hypothetical engine regression that archived a
protected sender therefore surfaces as an error here — never as a silent success.

All engine wrapping happens through the same entry points the CLI uses
(``get_provider`` / ``run_labeler`` / ``is_protected_sender`` / ``AuditLog``),
so the engine's existing test coverage and guarantees carry into the API.
"""

from __future__ import annotations

import dataclasses
import logging
from enum import Enum
from typing import Any, Callable, Optional

from core.audit import AuditInvariantError, AuditLog
from core.rules import categorize_with_tier, is_protected_sender

logger = logging.getLogger(__name__)

# Imported at module scope (not bound as default args) so tests can monkeypatch
# them and so run_triage always resolves the current module global.
from cli import get_provider, run_labeler


class ProviderUnavailable(RuntimeError):
    """Raised when a provider cannot be constructed or connected (e.g. missing
    credentials). The API maps this to HTTP 503 rather than a 500."""


# Re-export so the API layer can catch the gate-violation type from one place.
__all__ = [
    "check_sender",
    "run_triage",
    "ProviderUnavailable",
    "AuditInvariantError",
]


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion of engine objects (dataclasses, enums) to JSON."""
    if isinstance(obj, Enum):
        return obj.value if not isinstance(obj.value, Enum) else obj.name
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    return obj


def check_sender(sender: str, subject: str = "") -> dict:
    """Pure, mailbox-free check: would this sender be protected, and how is it
    categorized? Backs the demo / trust surface and needs no credentials."""
    protected = bool(is_protected_sender(sender))
    categorization: Optional[dict]
    try:
        categorization = _jsonable(categorize_with_tier(sender, subject))
    except Exception:  # categorization is advisory; never block the protect-check
        categorization = None
    return {"sender": sender, "protected": protected, "categorization": categorization}


def run_triage(
    *,
    provider: str = "gmail",
    query: str = "has:nouserlabels",
    limit: int = 100,
    dry_run: bool = True,
    remove_label: Optional[str] = None,
    tier_routing: bool = False,
    vip_only: bool = False,
    audit_path: Optional[str] = None,
    provider_factory: Optional[Callable[..., Any]] = None,
) -> dict:
    """Run (or preview) a triage and return the receipt + audit summary.

    Fail-closed: if the independent audit trail proves a protected sender left
    the inbox, :meth:`AuditLog.assert_no_violations` raises
    :class:`AuditInvariantError` and this function never returns a success body.
    """
    factory = provider_factory or get_provider
    # Build + connect are wrapped together: an unknown provider raises ValueError
    # from the factory, and a missing-credentials / network failure raises from
    # connect(). Both must map to a clean ProviderUnavailable (-> 503), never an
    # unhandled exception (-> 500) or a leaked internal error string.
    #
    # The raw exception text can contain sensitive internals — credential file
    # paths (e.g. the OAuth token cache), 1Password item references, hostnames,
    # and stack-trace fragments. It is logged server-side for operators but NEVER
    # returned to the client; the client gets a fixed, generic message.
    try:
        prov = factory(provider)
        prov.connect()
    except Exception as e:  # missing creds / network / unknown provider
        logger.warning("provider %r unavailable: %s", provider, e, exc_info=True)
        raise ProviderUnavailable(
            "provider is not available (check server configuration/credentials)"
        ) from e

    audit = AuditLog(path=audit_path, provider=provider, dry_run=dry_run)
    try:
        result = run_labeler(
            prov,
            query=query,
            limit=limit,
            dry_run=dry_run,
            remove_label=remove_label,
            state_file=None,
            tier_routing=tier_routing,
            vip_only=vip_only,
            audit=audit,
        )
    finally:
        try:
            prov.disconnect()
        except Exception:
            pass

    # Fail-closed safety boundary — independent of the engine's own gate.
    audit.assert_no_violations()

    return {
        "dry_run": dry_run,
        "provider": provider,
        "receipt": audit.receipt_line(),
        "audit": audit.summary(),
        "processed": _jsonable(result),
    }
