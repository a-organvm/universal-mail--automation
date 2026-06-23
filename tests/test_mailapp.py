"""Mail.app provider regressions."""

from datetime import datetime

from core.models import LabelAction
from providers.mailapp import MailAppProvider


def test_mailapp_star_accepts_due_date_from_base_apply_actions():
    provider = MailAppProvider()
    scripts = []
    provider._run_applescript = lambda script: scripts.append(script) or "ok"

    result = provider.apply_actions([
        LabelAction(
            message_id="123",
            sender="promo@some-shop.example",
            star=True,
            due_date=datetime(2026, 6, 1),
        )
    ])

    assert result.error_count == 0
    assert result.success_count == 1
    assert scripts and "flagged status" in scripts[0]
