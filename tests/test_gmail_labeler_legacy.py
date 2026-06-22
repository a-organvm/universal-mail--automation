"""Focused offline coverage for the legacy Gmail labeler.

The module is intentionally relabel-only and deprecated, but it remains a
shipped top-level module. These tests keep its standalone Gmail API plumbing
honest without importing real Google client libraries or touching OAuth state.
"""

import importlib
import sys
import types

import pytest


@pytest.fixture()
def legacy_labeler(monkeypatch):
    errors_mod = types.ModuleType("googleapiclient.errors")

    class FakeHttpError(Exception):
        pass

    errors_mod.HttpError = FakeHttpError

    google_mod = types.ModuleType("googleapiclient")
    google_mod.errors = errors_mod

    auth_mod = types.ModuleType("gmail_auth")
    auth_mod.build_gmail_service = lambda scopes=None: {"scopes": scopes}

    monkeypatch.setitem(sys.modules, "googleapiclient", google_mod)
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", errors_mod)
    monkeypatch.setitem(sys.modules, "gmail_auth", auth_mod)
    sys.modules.pop("gmail_labeler_legacy", None)

    module = importlib.import_module("gmail_labeler_legacy")
    yield module

    sys.modules.pop("gmail_labeler_legacy", None)


class _Request:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.response


class _FlakyRequest:
    def __init__(self, failures, response):
        self.failures = list(failures)
        self.response = response
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return self.response


def _email(sender, subject):
    return {
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ]
        }
    }


class _LabelService:
    def __init__(self, labels):
        self._labels = labels
        self.created = []

    def users(self):
        return self

    def labels(self):
        return self

    def list(self, **kwargs):
        return _Request({"labels": self._labels})

    def create(self, **kwargs):
        self.created.append(kwargs["body"])
        return _Request({"id": "new-label-id"})


class _MessageService:
    def __init__(self, pages, metadata):
        self.pages = list(pages)
        self.metadata = metadata
        self.list_calls = []
        self.get_calls = []
        self.modify_calls = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Request(self.pages.pop(0) if self.pages else {"messages": []})

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _Request(self.metadata[kwargs["id"]])

    def modify(self, **kwargs):
        self.modify_calls.append({"id": kwargs["id"], "body": kwargs["body"]})
        return _Request({})


def test_get_gmail_service_delegates_with_modify_scope(legacy_labeler):
    assert legacy_labeler.get_gmail_service() == {"scopes": legacy_labeler.SCOPES}


def test_categorize_email_uses_lowest_priority_matching_rule(legacy_labeler):
    data = _email(
        "GitHub <notifications@github.com>",
        "Your Chase statement is ready",
    )

    assert legacy_labeler.categorize_email(data) == "Dev/GitHub"


def test_categorize_email_falls_back_to_uncategorized(legacy_labeler):
    data = _email("Friend <friend@example.test>", "Lunch next week")

    assert legacy_labeler.categorize_email(data) == "Uncategorized"


def test_execute_with_retry_backs_off_then_returns(monkeypatch, legacy_labeler):
    sleeps = []
    monkeypatch.setattr(legacy_labeler.time, "sleep", sleeps.append)
    request = _FlakyRequest([OSError("temporary"), RuntimeError("again")], {"ok": True})

    assert legacy_labeler.execute_with_retry(request, retries=3, base_sleep=0.25) == {"ok": True}
    assert request.calls == 3
    assert sleeps == [0.25, 0.5]


def test_execute_with_retry_raises_after_final_attempt(monkeypatch, legacy_labeler):
    monkeypatch.setattr(legacy_labeler.time, "sleep", lambda _seconds: None)
    request = _FlakyRequest([OSError("one"), OSError("two")], {"unreachable": True})

    with pytest.raises(OSError, match="two"):
        legacy_labeler.execute_with_retry(request, retries=2, base_sleep=0.01)

    assert request.calls == 2


def test_get_or_create_label_reuses_existing_label(legacy_labeler):
    service = _LabelService([{"name": "Dev/GitHub", "id": "existing-id"}])

    assert legacy_labeler.get_or_create_label(service, "Dev/GitHub") == "existing-id"
    assert service.created == []


def test_get_or_create_label_creates_missing_label(legacy_labeler):
    service = _LabelService([])

    assert legacy_labeler.get_or_create_label(service, "Finance/Payments") == "new-label-id"
    assert service.created == [
        {
            "name": "Finance/Payments",
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
    ]


def test_label_all_unlabeled_emails_labels_pages_and_removes_uncategorized(monkeypatch, legacy_labeler):
    label_ids = {name: f"label-{idx}" for idx, name in enumerate(legacy_labeler.LABEL_RULES, start=1)}
    monkeypatch.setattr(legacy_labeler, "get_or_create_label", lambda _service, name: label_ids[name])
    monkeypatch.setattr(legacy_labeler.time, "sleep", lambda _seconds: None)

    service = _MessageService(
        pages=[
            {"messages": [{"id": "m-github"}, {"id": "m-other"}], "nextPageToken": "next-page"},
            {"messages": []},
        ],
        metadata={
            "m-github": _email("GitHub <notifications@github.com>", "Build finished"),
            "m-other": _email("Friend <friend@example.test>", "Lunch next week"),
        },
    )

    stats = legacy_labeler.label_all_unlabeled_emails(
        service,
        batch_size=2,
        query="label:Uncategorized",
    )

    assert service.list_calls == [
        {
            "userId": "me",
            "q": "label:Uncategorized",
            "maxResults": 2,
            "pageToken": None,
        },
        {
            "userId": "me",
            "q": "label:Uncategorized",
            "maxResults": 2,
            "pageToken": "next-page",
        },
    ]
    assert service.get_calls == [
        {
            "userId": "me",
            "id": "m-github",
            "format": "metadata",
            "metadataHeaders": ["From", "Subject"],
        },
        {
            "userId": "me",
            "id": "m-other",
            "format": "metadata",
            "metadataHeaders": ["From", "Subject"],
        },
    ]
    assert service.modify_calls == [
        {
            "id": "m-github",
            "body": {
                "addLabelIds": [label_ids["Dev/GitHub"]],
                "removeLabelIds": [label_ids["Uncategorized"]],
            },
        },
        {
            "id": "m-other",
            "body": {"addLabelIds": [label_ids["Uncategorized"]]},
        },
    ]
    assert dict(stats) == {"Dev/GitHub": 1, "Uncategorized": 1}


def test_verify_labeling_complete_reports_remaining_state(legacy_labeler):
    complete = _MessageService([{"resultSizeEstimate": 0}], {})
    incomplete = _MessageService([{"resultSizeEstimate": 3}], {})

    assert legacy_labeler.verify_labeling_complete(complete) is True
    assert legacy_labeler.verify_labeling_complete(incomplete) is False
