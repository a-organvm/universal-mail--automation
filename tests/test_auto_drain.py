"""Tests for auto_drain dry-run guard (review U045).

The defect: auto_drain.py executed its destructive bulk label moves
IMMEDIATELY on invocation — no --apply, no dry-run, in contrast to its
sibling icloud_triage.py which is dry-run by default. The invariant these
tests enforce: without apply=True (CLI --apply), drain_loop NEVER calls
batchModify, and a dry run is exactly ONE analysis pass (it cannot loop,
because nothing it does can empty the source bucket).
"""

import pytest

pytest.importorskip("googleapiclient", reason="googleapiclient dependency is required for auto_drain tests")
import auto_drain


class _Req:
    """Stands in for a googleapiclient request: .execute() yields the response."""

    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class FakeBatch:
    def __init__(self, callback):
        self._callback = callback
        self._responses = []

    def add(self, response):
        # FakeService.get() returns the metadata response directly.
        self._responses.append(response)

    def execute(self):
        for i, resp in enumerate(self._responses):
            self._callback(str(i), resp, None)


class FakeService:
    """Minimal Gmail-service double for drain_loop.

    ``batch_modify_bodies`` is the tripwire: any entry means a real bulk
    move would have been executed against the account.
    """

    def __init__(self, labels, headers, sample_batches, search_results=None):
        self._labels = labels                  # name -> id
        self._headers = headers                # msg_id -> (sender, subject)
        self._sample_batches = list(sample_batches)
        self._search_results = dict(search_results or {})
        self.batch_modify_bodies = []
        self.sample_list_calls = 0

    # the googleapiclient fluent chain ---------------------------------
    def users(self):
        return self

    def labels(self):
        return self

    def messages(self):
        return self

    def list(self, userId=None, labelIds=None, q=None, maxResults=None):
        if labelIds is not None:               # sample of the source bucket
            self.sample_list_calls += 1
            resp = (self._sample_batches.pop(0)
                    if self._sample_batches else {"messages": []})
            return _Req(resp)
        if q is not None:                      # per-domain bulk search
            return _Req(self._search_results.get(q, {"messages": []}))
        return _Req({"labels": [{"name": n, "id": i}
                                for n, i in self._labels.items()]})

    def get(self, userId=None, id=None, format=None, metadataHeaders=None):
        sender, subject = self._headers[id]
        return {"payload": {"headers": [
            {"name": "From", "value": sender},
            {"name": "Subject", "value": subject},
        ]}}

    def new_batch_http_request(self, callback=None):
        return FakeBatch(callback)

    def batchModify(self, userId=None, body=None):
        self.batch_modify_bodies.append(body)
        return _Req({})


# NOTE: classify_domain checks KEYWORDS in dict order and matches substrings,
# so "payment" hits Finance/Banking's "pay" term before Finance/Payments is
# consulted — the fixture must carry the label the classifier actually picks.
_LABELS = {"Misc/Other": "L_misc", "Finance/Banking": "L_finbank",
           "Notification": "L_notif"}


def _service(sample_batches, **kw):
    headers = {
        "m1": ("Billing <billing@stripe.com>", "Your receipt from Acme"),
        "m2": ("Stripe <invoices@stripe.com>", "Invoice #42 payment"),
    }
    return FakeService(_LABELS, headers, sample_batches, **kw)


# -- the load-bearing invariant: dry run never mutates ----------------------
def test_dry_run_default_never_calls_batchmodify():
    svc = _service([{"messages": [{"id": "m1"}, {"id": "m2"}]}])
    auto_drain.drain_loop(service=svc)         # apply defaults to False
    assert svc.batch_modify_bodies == [], (
        "dry-run drain_loop executed a bulk move (review U045)")


def test_dry_run_is_exactly_one_pass():
    # Nothing moves in a dry run, so the bucket can never empty: looping
    # would run forever. The guard must break after one analysis pass even
    # though more (identical) samples are queued up.
    batches = [{"messages": [{"id": "m1"}]}] * 5
    svc = _service(batches)
    auto_drain.drain_loop(service=svc)
    assert svc.sample_list_calls == 1
    assert svc.batch_modify_bodies == []


def test_missing_source_label_no_moves():
    svc = FakeService({"Notification": "L_notif"}, {}, [])
    auto_drain.drain_loop(service=svc, apply=True)
    assert svc.batch_modify_bodies == []


# -- apply mode still performs the move (the guard must not break it) --------
def test_apply_performs_bulk_move(monkeypatch):
    monkeypatch.setattr(auto_drain.time, "sleep", lambda s: None)
    query = "from:stripe.com label:Misc/Other"
    svc = _service(
        # first sample has mail; second is empty so the loop terminates
        [{"messages": [{"id": "m1"}, {"id": "m2"}]}, {"messages": []}],
        search_results={query: {"messages": [{"id": "m1"}, {"id": "m2"}]}},
    )
    auto_drain.drain_loop(service=svc, apply=True)
    assert svc.batch_modify_bodies == [{
        "ids": ["m1", "m2"],
        "addLabelIds": ["L_finbank"],          # "payment" matches Banking's "pay"
        "removeLabelIds": ["L_misc"],
    }]


# -- CLI wiring ---------------------------------------------------------------
def test_main_default_is_dry_run(monkeypatch):
    seen = {}
    monkeypatch.setattr(auto_drain, "drain_loop",
                        lambda apply=False, **kw: seen.setdefault("apply", apply))
    auto_drain.main([])
    assert seen["apply"] is False


def test_main_apply_flag(monkeypatch):
    seen = {}
    monkeypatch.setattr(auto_drain, "drain_loop",
                        lambda apply=False, **kw: seen.setdefault("apply", apply))
    auto_drain.main(["--apply"])
    assert seen["apply"] is True
