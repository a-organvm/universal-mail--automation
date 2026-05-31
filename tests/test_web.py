"""Tests for the static web dashboard served by the API app."""

from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def test_dashboard_served():
    r = client.get("/app/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Universal Mail Automation" in r.text


def test_root_redirects_to_dashboard():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert r.headers["location"] == "/app/"


def test_dashboard_does_not_shadow_api():
    # The static mount must not break the JSON API.
    assert client.get("/health").status_code == 200
    r = client.post("/v1/senders/check", json={"sender": "clerk@courts.ca.gov"})
    assert r.status_code == 200 and r.json()["protected"] is True
