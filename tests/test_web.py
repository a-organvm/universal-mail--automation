"""Tests for the static web dashboard served by the API app."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)
WEB_HTML = Path("web/index.html").read_text()


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


def test_dashboard_developer_links_resolve():
    assert client.get("/docs").status_code == 200
    assert client.get("/llms.txt").status_code == 200
    assert client.get("/.well-known/agent.json").status_code == 200
    assert client.get("/health").status_code == 200

    r = client.get("/server.json")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "io.github.a-organvm/universal-mail-automation"
    assert body["remotes"][0]["url"] == "http://testserver/mcp"


def test_dashboard_interactive_controls_use_real_api_states():
    assert "localSenderCheck" not in WEB_HTML
    assert "localPreviewResult" not in WEB_HTML
    assert "This share link is running in static mode" not in WEB_HTML
    assert 'data-sender=""' in WEB_HTML
    assert "Cannot reach the API" in WEB_HTML
    assert 'href="/server.json">MCP registry' in WEB_HTML


def test_dashboard_defines_status_color_tokens():
    for token in ("--green:", "--green-2:", "--green-soft:"):
        assert token in WEB_HTML
