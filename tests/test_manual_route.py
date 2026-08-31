"""The /manual page and search API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from connector.main import app

client = TestClient(app)


def test_manual_index_serves() -> None:
    response = client.get("/manual")
    assert response.status_code == 200
    assert "BBS Manual" in response.text


def test_manual_index_links_every_section() -> None:
    body = client.get("/manual").text
    assert "Setting up RaceManager access" in body
    assert "Best practices for race day" in body


def test_manual_topic_serves_with_the_sidebar() -> None:
    response = client.get("/manual/sqorz-live-timing")
    assert response.status_code == 200
    assert "manual-nav" in response.text
    assert "Sqorz Live Timing" in response.text


def test_manual_topic_marks_the_active_sidebar_entry() -> None:
    body = client.get("/manual/faq").text
    assert '<li class="active"><a href="/manual/faq">' in body


def test_manual_unknown_topic_redirects_to_the_index() -> None:
    response = client.get("/manual/not-a-real-topic", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/manual"


def test_manual_has_no_external_script_or_font_reference() -> None:
    """Fully offline -- same rule as the overlays: no CDN, no external
    fonts."""
    body = client.get("/manual").text
    assert "cdn." not in body.lower()
    assert "fonts.googleapis" not in body
    assert "fonts.gstatic" not in body


def test_manual_search_endpoint() -> None:
    response = client.get("/api/manual/search", params={"q": "keyboard"})
    assert response.status_code == 200
    hits = response.json()
    assert any(h["slug"] == "keyboard-shortcuts" for h in hits)


def test_manual_search_endpoint_empty_query() -> None:
    response = client.get("/api/manual/search", params={"q": ""})
    assert response.json() == []


def test_manual_search_is_wired_into_every_page() -> None:
    body = client.get("/manual/faq").text
    assert 'id="manual-search"' in body
