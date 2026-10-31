"""Regression tests for the public landing route `/` (routes.md #1, issue #49)."""

import pytest

from .conftest import HTMX

pytestmark = pytest.mark.django_db

LANDING_LINKS = ["/cont/inregistrare/", "/carti/", "/cont/intrare/"]


def test_reverse_home_is_root():
    from django.urls import reverse

    assert reverse("home") == "/"


def test_anonymous_get_home_renders_public_landing(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "adult/landing.html" in [t.name for t in response.templates]
    content = response.content.decode()
    for link in LANDING_LINKS:
        assert link in content
    assert "/panou/" not in content  # no adult dashboard CTA for anonymous visitors


def test_anonymous_post_home_is_405(client):
    assert client.post("/").status_code == 405


def test_adult_get_home_renders_same_landing_with_adult_cta(adult_client):
    # Explicit decision: a signed-in adult sees the same landing; the template shows adult CTAs.
    response = adult_client.get("/")
    assert response.status_code == 200
    assert "adult/landing.html" in [t.name for t in response.templates]
    content = response.content.decode()
    assert "/panou/" in content and "/raft/" in content


def test_child_mode_home_fails_closed_to_pin_gate(child_client):
    # "home" is deliberately NOT in CHILD_ALLOWED: a child must never see the adult landing.
    response = child_client.get("/")
    assert response.status_code == 302 and response["Location"] == "/parinte/"


def test_child_mode_home_via_htmx_is_403_without_partial(child_client):
    response = child_client.get("/", **HTMX)
    assert response.status_code == 403 and response.content == b""
    assert "HX-Trigger" not in response
