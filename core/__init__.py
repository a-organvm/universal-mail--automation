"""
Core email automation module.

Provides shared categorization rules, state management, and data models
used across all email providers (Gmail, IMAP, Mail.app, Outlook).
"""

__version__ = "0.2.0"

from core.models import EmailMessage, LabelAction, ProcessingResult
from core.rules import (
    LABEL_RULES,
    PRIORITY_LABELS,
    KEEP_IN_INBOX,
    PRIORITY_TIERS,
    VIP_SENDERS,
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
    is_vip_sender,
    check_vip_sender,
    get_vip_senders,
    add_vip_sender,
    escalate_by_age,
    calculate_email_age_hours,
    PROTECTED_SENDERS,
    is_protected_sender,
    is_archivable,
    partition_protected,
    normalize_sender,
)
from core.research import ResearchDossier, research_message
from core.voice import (
    VoiceProfile,
    learn_voice_profile,
    default_voice_profile,
    load_voice_profile,
    save_voice_profile,
)
from core.triage import (
    TriageItem,
    triage_messages,
    score_priority,
    render_triage,
)
from core.state import StateManager
from core.config import Config, load_config, create_sample_config

__all__ = [
    "__version__",
    "EmailMessage",
    "LabelAction",
    "ProcessingResult",
    "LABEL_RULES",
    "PRIORITY_LABELS",
    "KEEP_IN_INBOX",
    "PRIORITY_TIERS",
    "VIP_SENDERS",
    "PriorityTier",
    "VIPSender",
    "CategorizationResult",
    "categorize_message",
    "categorize_from_strings",
    "categorize_with_tier",
    "get_tier_for_label",
    "get_tier_config",
    "should_star",
    "should_keep_in_inbox",
    "is_time_sensitive",
    "is_vip_sender",
    "check_vip_sender",
    "get_vip_senders",
    "add_vip_sender",
    "EscalationResult",
    "escalate_by_age",
    "calculate_email_age_hours",
    "PROTECTED_SENDERS",
    "is_protected_sender",
    "is_archivable",
    "partition_protected",
    "normalize_sender",
    "ResearchDossier",
    "research_message",
    "VoiceProfile",
    "learn_voice_profile",
    "default_voice_profile",
    "load_voice_profile",
    "save_voice_profile",
    "TriageItem",
    "triage_messages",
    "score_priority",
    "render_triage",
    "StateManager",
    "Config",
    "load_config",
    "create_sample_config",
]
