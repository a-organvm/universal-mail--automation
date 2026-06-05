"""Tests for OutlookProvider error honesty (review U097).

The defect class: Graph API failures were disguised as benign domain values —
``list_messages`` swallowed any exception into ``ListMessagesResult(messages=[])``
(the CLI reads empty as "no more messages" and reports a silently-truncated
run as success), ``get_message_details`` returned None on ANY error (an
expired token silently skipped every message), and ``apply_category``'s
failed current-categories GET fabricated ``current_cats=[]`` which the PATCH
then wrote back, clobbering every category already on the message.

Invariants enforced here:
  * list_messages NEVER converts an API error into an empty (success-shaped) result.
  * get_message_details returns None ONLY for 404 (the not-found contract);
    every other failure raises.
  * apply_category never PATCHes categories it could not read first.
"""

import pytest

from providers.outlook import OutlookProvider


class _FakeHTTPError(Exception):
    """Stands in for requests.HTTPError: carries .response.status_code."""

    class _Resp:
        def __init__(self, status_code):
            self.status_code = status_code

    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = self._Resp(status_code)


def _provider():
    return OutlookProvider(client_id="test-client-id")


def _raise(exc):
    def _inner(*args, **kwargs):
        raise exc
    return _inner


# -- list_messages: errors must propagate, not become empty results ----------
@pytest.mark.parametrize("exc", [
    _FakeHTTPError(401),     # expired/invalid token
    _FakeHTTPError(429),     # throttled mid-pagination
    _FakeHTTPError(503),     # transient server error
    ConnectionError("network down"),
])
def test_list_messages_raises_instead_of_empty_result(monkeypatch, exc):
    p = _provider()
    monkeypatch.setattr(p, "_api_get", _raise(exc))
    with pytest.raises(type(exc)):
        p.list_messages(limit=10)


def test_list_messages_genuinely_empty_is_still_empty(monkeypatch):
    # An OK response with no messages is the legitimate empty case.
    p = _provider()
    monkeypatch.setattr(p, "_api_get", lambda url, params=None: {"value": []})
    result = p.list_messages(limit=10)
    assert result.messages == []
    assert result.next_page_token is None


def test_list_messages_parses_messages_on_success(monkeypatch):
    p = _provider()
    payload = {
        "value": [{
            "id": "m1",
            "subject": "Hello",
            "from": {"emailAddress": {"name": "A", "address": "a@example.com"}},
            "isRead": False,
            "flag": {"flagStatus": "flagged"},
            "receivedDateTime": "2026-06-01T00:00:00Z",
        }],
        "@odata.nextLink": "https://graph.microsoft.com/next",
    }
    monkeypatch.setattr(p, "_api_get", lambda url, params=None: payload)
    result = p.list_messages(limit=10)
    assert [m.id for m in result.messages] == ["m1"]
    assert result.messages[0].is_starred is True
    assert result.next_page_token == "https://graph.microsoft.com/next"


# -- get_message_details: None is ONLY for 404 -------------------------------
def test_get_message_details_none_on_404(monkeypatch):
    p = _provider()
    monkeypatch.setattr(p, "_api_get", _raise(_FakeHTTPError(404)))
    assert p.get_message_details("gone") is None


@pytest.mark.parametrize("exc", [
    _FakeHTTPError(401),
    _FakeHTTPError(429),
    _FakeHTTPError(500),
    ConnectionError("network down"),
])
def test_get_message_details_raises_on_non_404(monkeypatch, exc):
    p = _provider()
    monkeypatch.setattr(p, "_api_get", _raise(exc))
    with pytest.raises(type(exc)):
        p.get_message_details("m1")


# -- apply_category: never clobber categories it could not read --------------
def test_apply_category_fails_closed_when_get_fails(monkeypatch):
    p = _provider()
    monkeypatch.setattr(p, "ensure_category_exists", lambda *a, **k: "cat-id")
    monkeypatch.setattr(p, "_api_get", _raise(_FakeHTTPError(503)))
    patches = []
    monkeypatch.setattr(p, "_api_patch",
                        lambda url, data: patches.append(data) or {})
    assert p.apply_category("m1", "Work") is False
    assert patches == [], (
        "apply_category PATCHed a fabricated category list after a failed GET "
        "— this overwrites the message's existing categories (review U097)")


def test_apply_category_preserves_existing_categories(monkeypatch):
    p = _provider()
    monkeypatch.setattr(p, "ensure_category_exists", lambda *a, **k: "cat-id")
    monkeypatch.setattr(
        p, "_api_get",
        lambda url, params=None: {"categories": ["Personal", "Finance"]})
    patches = []
    monkeypatch.setattr(p, "_api_patch",
                        lambda url, data: patches.append(data) or {})
    assert p.apply_category("m1", "Work") is True
    assert patches == [{"categories": ["Personal", "Finance", "Work"]}]


def test_apply_category_false_when_patch_fails(monkeypatch):
    p = _provider()
    monkeypatch.setattr(p, "ensure_category_exists", lambda *a, **k: "cat-id")
    monkeypatch.setattr(p, "_api_get",
                        lambda url, params=None: {"categories": []})
    monkeypatch.setattr(p, "_api_patch", _raise(_FakeHTTPError(500)))
    assert p.apply_category("m1", "Work") is False
