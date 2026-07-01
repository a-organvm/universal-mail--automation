"""Live-run entitlement reservation for HTTP triage mutations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from api import plans
from api.store import AccountRow, get_store


class EntitlementExhausted(RuntimeError):
    """Raised when an account cannot reserve or buy another live run."""


class ProviderNotAllowed(RuntimeError):
    """Raised when the account plan does not include the requested provider."""


def current_period_key(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


@dataclass
class LiveRunReservation:
    account_id: str
    period: str
    used_credit: bool = False
    used_monthly_allowance: bool = False
    committed: bool = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        if self.committed:
            return
        store = get_store()
        if self.used_credit:
            store.add_credits(self.account_id, 1)
        if self.used_monthly_allowance:
            store.refund_live_run(self.account_id, self.period)


def provider_allowed(entitlements: dict, provider: str) -> bool:
    if entitlements.get("providers") == "all":
        return True
    return (provider or "gmail").lower() in {"gmail", "fake"}


def reserve_live_run(
    account: AccountRow, *, provider: str = "gmail"
) -> LiveRunReservation:
    """Reserve entitlement before a live mailbox mutation.

    Monthly plan allowance is used first. If the monthly cap is exhausted, a
    prepaid run credit can cover the run. Dry-runs do not call this path.
    """
    store = get_store()
    account_id = account["id"]
    period = current_period_key()
    entitlements = plans.entitlements_for(account)
    if not provider_allowed(entitlements, provider):
        raise ProviderNotAllowed("provider is not included in this plan")

    if store.reserve_live_run(account_id, period, entitlements["monthly_run_cap"]):
        return LiveRunReservation(
            account_id=account_id, period=period, used_monthly_allowance=True
        )

    if int(entitlements.get("run_credits", 0)) > 0 and store.consume_credit(
        account_id, 1
    ):
        return LiveRunReservation(account_id=account_id, period=period, used_credit=True)

    raise EntitlementExhausted("run entitlement exhausted")
