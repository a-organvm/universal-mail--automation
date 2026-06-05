"""Tests for core.rules — categorization, tiers, VIP senders, escalation."""

from datetime import datetime, timezone, timedelta

import pytest

from core.rules import (
    is_protected_sender,
    normalize_sender,
    LABEL_RULES,
    PRIORITY_LABELS,
    KEEP_IN_INBOX,
    PRIORITY_TIERS,
    PriorityTier,
    VIPSender,
    CategorizationResult,
    EscalationResult,
    categorize_message,
    categorize_from_strings,
    categorize_with_tier,
    get_tier_for_label,
    get_tier_config,
    should_star,
    should_keep_in_inbox,
    is_time_sensitive,
    check_vip_sender,
    is_vip_sender,
    get_vip_senders,
    add_vip_sender,
    escalate_by_age,
    calculate_email_age_hours,
    VIP_SENDERS,
    _find_best_label,
)


class TestLabelRulesStructure:
    def test_rules_is_nonempty_dict(self):
        assert isinstance(LABEL_RULES, dict)
        assert len(LABEL_RULES) > 10

    def test_every_rule_has_required_keys(self):
        for label, rule in LABEL_RULES.items():
            assert "patterns" in rule, f"{label} missing 'patterns'"
            assert "priority" in rule, f"{label} missing 'priority'"
            assert isinstance(rule["patterns"], list), f"{label} patterns must be list"
            assert isinstance(rule["priority"], int), f"{label} priority must be int"

    def test_misc_other_is_catch_all(self):
        assert "Misc/Other" in LABEL_RULES
        assert LABEL_RULES["Misc/Other"]["priority"] == 999

    def test_unique_priorities_where_expected(self):
        """Each rule should have a priority; duplicates are allowed but verify top rules."""
        priorities = [r["priority"] for r in LABEL_RULES.values()]
        assert LABEL_RULES["Dev/GitHub"]["priority"] == 1


class TestPriorityTiers:
    def test_four_tiers_defined(self):
        assert set(PRIORITY_TIERS.keys()) == {1, 2, 3, 4}

    def test_tier_1_is_critical(self):
        t = PRIORITY_TIERS[1]
        assert t.name == "Critical"
        assert t.star is True
        assert t.keep_in_inbox is True
        assert t.folder == "Action/Critical"

    def test_tier_4_is_reference(self):
        t = PRIORITY_TIERS[4]
        assert t.name == "Reference"
        assert t.star is False
        assert t.keep_in_inbox is False
        assert t.folder is None

    def test_priority_tier_frozen(self):
        t = PRIORITY_TIERS[1]
        try:
            t.name = "Changed"
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestCategorizeMessage:
    """Test categorize_message() which takes Gmail-style headers."""

    def test_github_notification(self):
        headers = [
            {"name": "From", "value": "notifications@github.com"},
            {"name": "Subject", "value": "[repo] PR review"},
        ]
        assert categorize_message(headers) == "Dev/GitHub"

    def test_chase_banking(self):
        headers = [
            {"name": "From", "value": "alerts@chase.com"},
            {"name": "Subject", "value": "Account alert"},
        ]
        assert categorize_message(headers) == "Finance/Banking"

    def test_unknown_falls_to_misc(self):
        headers = [
            {"name": "From", "value": "random@unknowndomain.xyz"},
            {"name": "Subject", "value": "Nothing special"},
        ]
        assert categorize_message(headers) == "Misc/Other"

    def test_empty_headers(self):
        assert categorize_message([]) == "Misc/Other"

    def test_case_insensitive(self):
        headers = [
            {"name": "from", "value": "NOTIFICATIONS@GITHUB.COM"},
            {"name": "subject", "value": "PR REVIEW"},
        ]
        assert categorize_message(headers) == "Dev/GitHub"


class TestCategorizeFromStrings:
    def test_github_sender(self):
        assert categorize_from_strings("notify@github.com", "PR") == "Dev/GitHub"

    def test_paypal_payment(self):
        assert categorize_from_strings("service@paypal.com", "Receipt") == "Finance/Payments"

    def test_security_alert(self):
        assert categorize_from_strings("noreply@1password.com", "Login") == "Tech/Security"

    def test_subject_pattern_match(self):
        """Subject-only patterns should match even with unknown sender."""
        assert categorize_from_strings("unknown@random.com", "Your data export is ready") == "AI/Data Exports"

    def test_priority_ordering(self):
        """Higher priority (lower number) rules should win over lower ones."""
        # "github.com" matches Dev/GitHub (priority 1)
        # Even if other patterns also match
        assert categorize_from_strings("notifications@github.com", "notification") == "Dev/GitHub"

    def test_shopping_patterns(self):
        assert categorize_from_strings("order@amazon.com", "Order confirmed") == "Shopping"

    def test_linkedin(self):
        assert categorize_from_strings("messages@linkedin.com", "New connection") == "Social/LinkedIn"


class TestCategorizeWithTier:
    def test_returns_categorization_result(self):
        result = categorize_with_tier("alerts@chase.com", "Statement ready")
        assert isinstance(result, CategorizationResult)
        assert result.label == "Finance/Banking"
        assert result.tier == 1
        assert result.time_sensitive is True
        assert result.is_vip is False

    def test_tier_config_matches(self):
        result = categorize_with_tier("noreply@github.com", "PR")
        assert result.tier_config == PRIORITY_TIERS[result.tier]

    def test_misc_other_tier(self):
        result = categorize_with_tier("nobody@nothing.xyz", "Blah")
        assert result.label == "Misc/Other"
        assert result.tier == 4
        assert result.time_sensitive is False

    def test_vip_sender_overrides_tier(self):
        add_vip_sender("test-vip", r"vip@special\.com", tier=1, star=True, note="Test VIP")
        result = categorize_with_tier("vip@special.com", "Regular subject")
        assert result.is_vip is True
        assert result.tier == 1
        assert result.vip_note == "Test VIP"

    def test_vip_with_label_override(self):
        add_vip_sender("override-test", r"boss@corp\.com", tier=1, star=True,
                        label_override="Personal", note="Boss")
        result = categorize_with_tier("boss@corp.com", "Meeting notes")
        assert result.label == "Personal"
        assert result.is_vip is True
        assert result.tier == 1


class TestVIPSenders:
    def test_add_vip_sender(self):
        add_vip_sender("test-key", r"test@vip\.com", tier=2, star=False, note="Test")
        vips = get_vip_senders()
        assert "test-key" in vips
        assert vips["test-key"].tier == 2

    def test_is_vip_sender(self):
        add_vip_sender("check-vip", r"vip@domain\.com", tier=1, star=True)
        assert is_vip_sender("vip@domain.com") is True
        assert is_vip_sender("nobody@other.com") is False

    def test_check_vip_sender_returns_tuple(self):
        add_vip_sender("tuple-test", r"boss@work\.com", tier=1, star=True, note="Boss")
        result = check_vip_sender("boss@work.com")
        assert result is not None
        vip, key = result
        assert key == "tuple-test"
        assert vip.note == "Boss"

    def test_check_vip_sender_case_insensitive(self):
        add_vip_sender("case-test", r"Admin@Company\.com", tier=1, star=True)
        assert check_vip_sender("ADMIN@company.com") is not None

    def test_get_vip_senders_returns_copy(self):
        vips = get_vip_senders()
        vips["hacker"] = VIPSender(pattern="x", tier=1, star=True)
        assert "hacker" not in VIP_SENDERS


class TestTierHelpers:
    def test_get_tier_for_label(self):
        assert get_tier_for_label("Finance/Banking") == 1
        assert get_tier_for_label("Dev/GitHub") == 2
        assert get_tier_for_label("Shopping") == 4

    def test_get_tier_for_unknown_label(self):
        assert get_tier_for_label("NonExistent/Label") == 4

    def test_get_tier_config(self):
        config = get_tier_config(1)
        assert config.name == "Critical"

    def test_get_tier_config_invalid(self):
        config = get_tier_config(99)
        assert config == PRIORITY_TIERS[4]  # Defaults to Reference

    def test_should_star_priority_labels(self):
        assert should_star("Finance/Banking") is True
        assert should_star("Tech/Security") is True

    def test_should_star_tier_based(self):
        # Personal is tier 1 which has star=True
        assert should_star("Personal") is True
        # Shopping is tier 4 which has star=False
        assert should_star("Shopping") is False

    def test_should_keep_in_inbox(self):
        assert should_keep_in_inbox("Finance/Banking") is True
        assert should_keep_in_inbox("Personal") is True
        assert should_keep_in_inbox("Shopping") is False

    def test_is_time_sensitive(self):
        assert is_time_sensitive("Finance/Banking") is True
        assert is_time_sensitive("Dev/Code-Review") is True
        assert is_time_sensitive("Shopping") is False
        assert is_time_sensitive("Entertainment") is False


class TestFindBestLabel:
    def test_priority_wins(self):
        """Lower priority number wins when multiple patterns match."""
        # "github.com notification" matches Dev/GitHub (1) and Notification (16)
        assert _find_best_label("github.com notification") == "Dev/GitHub"

    def test_catch_all(self):
        assert _find_best_label("completely unknown text") == "Misc/Other"


class TestEscalation:
    def test_tier_1_cannot_escalate(self):
        result = escalate_by_age(1, 100, is_time_sensitive=True)
        assert result.should_escalate is False
        assert result.escalated_tier == 1

    def test_no_escalation_under_24h(self):
        result = escalate_by_age(3, 12, is_time_sensitive=True)
        assert result.should_escalate is False
        assert result.escalated_tier == 3

    def test_time_sensitive_24_72h_escalates_tier_3_to_2(self):
        result = escalate_by_age(3, 48, is_time_sensitive=True)
        assert result.should_escalate is True
        assert result.original_tier == 3
        assert result.escalated_tier == 2

    def test_time_sensitive_24_72h_escalates_tier_4_to_2(self):
        result = escalate_by_age(4, 50, is_time_sensitive=True)
        assert result.should_escalate is True
        assert result.escalated_tier == 2

    def test_non_time_sensitive_24_72h_no_escalation(self):
        result = escalate_by_age(3, 48, is_time_sensitive=False)
        assert result.should_escalate is False

    def test_tier_2_no_escalation_24_72h(self):
        result = escalate_by_age(2, 48, is_time_sensitive=True)
        assert result.should_escalate is False

    def test_over_72h_always_escalates_to_tier_1(self):
        result = escalate_by_age(4, 100)
        assert result.should_escalate is True
        assert result.escalated_tier == 1

    def test_over_72h_tier_2_to_1(self):
        result = escalate_by_age(2, 80)
        assert result.should_escalate is True
        assert result.escalated_tier == 1

    def test_escalation_result_has_reason(self):
        result = escalate_by_age(3, 100)
        assert "hours old" in result.reason


class TestCalculateEmailAgeHours:
    def test_none_returns_zero(self):
        assert calculate_email_age_hours(None) == 0

    def test_recent_email(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        age = calculate_email_age_hours(recent)
        assert 1.9 < age < 2.5

    def test_old_email(self):
        old = datetime.now(timezone.utc) - timedelta(days=5)
        age = calculate_email_age_hours(old)
        assert 119 < age < 121

    def test_naive_datetime_assumed_utc(self):
        """Naive datetimes are treated as UTC by the function."""
        # Create a naive datetime that represents "1 hour ago in UTC"
        naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        age = calculate_email_age_hours(naive)
        assert 0.5 < age < 1.5


# Adversarial protected-gate vectors (from the 2026-05-31 hardening workflow).
# Each case asserts the FAIL-CLOSED never-archive gate parses + decodes the real
# sender before matching. Fail-open vectors (relay/encoded/punycode/self/multi-
# address) must be protected; fail-closed-wrong vectors (substring embeds,
# display-name/local-part spoofs, foreign/embedded .gov) must NOT be protected.
#
# SYNTHETIC FIXTURES ONLY — these exercise GENERIC properties (relay decode,
# RFC2047, punycode, boundary matching, gov terminal-label, gmail canonicalization).
# example-lawfirm.com / example-bank.com / example-nonprofit.org are shipped in
# EXAMPLE_PROTECTED_SENDERS; example-bank-marketing.com is deliberately NOT. No
# real contact of any user appears here (the real list lives in a gitignored file).
PROTECTED_GATE_CASES = [
    # (from_string, expected_protected, reason)
    # --- CONTRACT ---
    ("Lawyer <a@example-lawfirm.com>", True, "legal exact domain"),
    ("DocuSign <dse@docusign.net>", True, "e-sign generic domain"),
    ("SSA <noreply@ssa.gov>", True, ".gov terminal label"),
    ("Bank Alerts <alerts@alerts.example-bank.com>", True, "bank-alert subdomain in list"),
    ("Bank News <news@example-bank-marketing.com>", False, "marketing sibling, not in list"),
    ("Someone <someone.else@gmail.com>", False, "random gmail, not self"),
    ("Promo <promo@some-marketing.example>", False, "marketing, not protected"),
    # --- FAIL-OPEN fixes (CRITICAL/HIGH) ---
    ("Lawyer <example-lawfirm_com_8f3a2b@icloud.com>", True, "relay dots->underscores"),
    ("Bank <example-bank_com_77@icloud.com>", True, "relay short numeric token"),
    ("Lawyer <user_at_example-lawfirm_com_a1b2c3@icloud.com>", True, "relay _at_ form"),
    ("Bank <user_at_example-bank_com_x9z@privaterelay.appleid.com>", True, "privaterelay _at_ form"),
    ("Lawyer <example-lawfirm_com_tok_tok@icloud.com>", True, "MF-6 multi-segment relay token"),
    ("Apple <noreply@e.appleid.com>", True, "appleid.com subdomain"),
    ("Apple <id@privaterelay.appleid.com>", True, "privaterelay is appleid subdomain"),
    ("Gov <irs_gov_tok9f@icloud.com>", True, "relay-encoded .gov"),
    ("Me <youremail@gmail.com>", True, "self, gmail canonical"),
    ("Me <y.o.u.r.e.m.a.i.l@gmail.com>", True, "self, gmail dotted"),
    ("Me <youremail+invoices@gmail.com>", True, "self, plus-tag"),
    ("Me <youremail@googlemail.com>", True, "self via googlemail.com"),
    ("=?utf-8?B?TGVnYWw=?= <a@example-lawfirm.com>", True, "RFC2047 display, real domain protected"),
    ("Lawyer <a@x.y.example-lawfirm.com>", True, "deep subdomain of protected base"),
    # --- MF-5 multi-address From (union; protected in either position) ---
    ("Lawyer <a@example-lawfirm.com>, Assistant <b@evil-bulk.io>", True, "MF-5 protected FIRST"),
    ("Assistant <b@evil-bulk.io>, Lawyer <a@example-lawfirm.com>", True, "MF-5 protected SECOND"),
    ("Team: a@example-lawfirm.com;", True, "RFC5322 group syntax"),
    ("a@b@example-lawfirm.com", True, "multiple @, last-@ domain protected, fail-closed-safe"),
    ("Apple <noreply@xn--80ak6aa92e.com>", False, "punycode homoglyph != apple.com (not auto-trusted)"),
    # --- FAIL-CLOSED-WRONG fixes (MED/HIGH) ---
    ('"example-bank.com Security Alert" <statements@attacker-phish.example>', False, "display-name spoof"),
    ("Sales <x@pineapple.com>", False, "substring embed of generic apple.com"),
    ("News <x@notgoogle.com>", False, "substring embed of generic google.com"),
    ("Legal <a@example-lawfirm.com.attacker.example>", False, "subdomain left-label spoof"),
    ("X <a@notexample-lawfirm.com>", False, "left-substring of protected base"),
    ("Gov <noreply@irs.gov.attacker.com>", False, "gov embedded non-terminal"),
    ("UK <x@service.gov.uk>", False, "foreign gov, US-only rule"),
    ("Spoof <spoof.gov@evil.io>", False, "gov in local part only"),
    ('"example-bank.com"@attacker.example', False, "quoted local-part token"),
    # --- NORMALIZATION ---
    ("IRS <noreply@irs.gov.>", True, "trailing FQDN dot stripped"),
    ("NOREPLY@IRS.GOV", True, "uppercase, bare addr"),
    ("=?utf-8?Q?example-bank=2Ecom?= <billing@attacker.example>", False, "QP-encoded brand in display only"),
    # --- FAIL CLOSED on uncertainty ---
    ("", True, "empty -> fail closed"),
    (None, True, "None -> fail closed"),
    ("garbage no at sign", True, "unparseable -> fail closed"),
    # --- relay NON-protected senders decode but are NOT protected ---
    ("Cinema <gables_com_z1q@icloud.com>", False, "relay sender, decoded domain not in list"),
    ("Friend <friend_at_protonmail_com_aa11@icloud.com>", False, "relay protonmail friend"),
]


class TestProtectedSenderGate:
    @pytest.mark.parametrize("frm,expected,reason", PROTECTED_GATE_CASES)
    def test_gate(self, frm, expected, reason):
        assert is_protected_sender(frm) is expected, reason

    def test_normalize_recovers_relay_domain(self):
        assert normalize_sender("X <example-lawfirm_com_8f3a2b@icloud.com>")[2] == "example-lawfirm.com"

    def test_normalize_idna(self):
        d = normalize_sender("X <a@xn--80ak6aa92e.com>")[2]
        assert not d.startswith("xn--")  # decoded to U-label

    def test_display_name_never_protects(self):
        assert is_protected_sender('"alerts@example-bank.com" <attacker@evil.io>') is False


class TestGovernmentPriorityAndTieBreak:
    """Reviews U064/U065: government mail must categorize as tier-1 Critical.

    U065: irs.gov appeared in both Finance/Tax (priority 8) and
    Personal/Government (old priority 17) — the lower number won, demoting an
    actual IRS notice to tier 2. U064: same-priority ties were resolved by
    dict-insertion order, so an ssa.gov notice containing any bulk-mail
    keyword fell to Marketing (tier 4).
    """

    def test_irs_gov_is_government_critical_not_finance_tax(self):
        # The exact U065 reproduction.
        res = categorize_with_tier("IRS <noreply@irs.gov>", "Your tax refund status")
        assert res.label == "Personal/Government"
        assert res.tier == 1

    def test_ssa_gov_with_bulk_mail_keywords_stays_government(self):
        # The exact U064 reproduction: 'newsletter'/'unsubscribe' must not
        # demote a government sender to Marketing.
        res = categorize_with_tier(
            "Benefits <noreply@ssa.gov>",
            "newsletter: your benefits statement — unsubscribe here")
        assert res.label == "Personal/Government"
        assert res.tier == 1

    def test_tax_software_vendors_still_finance_tax(self):
        # Removing irs.gov from Finance/Tax must not orphan the vendor rules.
        for sender in ("TurboTax <no-reply@intuit.com>",
                       "H&R Block <offers@hrblock.com>"):
            res = categorize_with_tier(sender, "Your tax return is ready")
            assert res.label == "Finance/Tax", sender

    def test_plain_marketing_still_marketing(self):
        res = categorize_with_tier(
            "Shop <deals@retailer-example.com>",
            "newsletter: special offer just for you — unsubscribe")
        assert res.label == "Marketing"
        assert res.tier == 4

    def test_equal_priority_tie_breaks_on_tier_not_insertion_order(self):
        # General U064 guard, independent of the Personal/Government reprioritization:
        # among rules with the SAME priority, the more critical tier must win
        # regardless of where it sits in the dict.
        import core.rules as rules_mod
        try:
            rules_mod.LABEL_RULES["ZZZ/TestLow"] = {
                "patterns": [r"tiebreakprobe"], "priority": 555, "tier": 4,
                "time_sensitive": False,
            }
            rules_mod.LABEL_RULES["ZZZ/TestHigh"] = {
                "patterns": [r"tiebreakprobe"], "priority": 555, "tier": 1,
                "time_sensitive": False,
            }
            # tier-4 rule was inserted FIRST; tier-1 must still win the tie.
            assert _find_best_label("tiebreakprobe") == "ZZZ/TestHigh"
        finally:
            rules_mod.LABEL_RULES.pop("ZZZ/TestLow", None)
            rules_mod.LABEL_RULES.pop("ZZZ/TestHigh", None)

    def test_government_does_not_steal_dev_mail(self):
        # Priority 4 sits below the Dev rules; a normal GitHub notification
        # must remain Dev/GitHub.
        res = categorize_with_tier(
            "GitHub <notifications@github.com>", "PR review requested")
        assert res.label == "Dev/GitHub"
