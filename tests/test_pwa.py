import json
import struct
from pathlib import Path
import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Account, ChildProfile, Reader


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def child_session(db):
    """Real database-backed child session without mocking."""
    guardian = Account.objects.create_user(email="pwa_guardian@test.local", password="password123")
    guardian.pin_hash = "mock_hash"
    guardian.save()
    child = ChildProfile.objects.create(
        guardian=guardian,
        nickname="Matei",
        avatar="fox",
        age_band="7-8",
    )
    Reader.objects.create(account=None, child=child, kind=Reader.CHILD)
    client = Client()
    client.force_login(guardian)
    session = client.session
    session["mode"] = "child"
    session["active_child"] = str(child.public_id)
    session.save()
    return client, guardian, child


def test_pwa_url_reverses():
    """Verify URL names match CHILD_ALLOWED contract in apps/accounts/middleware.py."""
    assert reverse("manifest") == "/manifest.webmanifest"
    assert reverse("sw") == "/sw.js"
    assert reverse("offline") == "/offline/"


def test_manifest_endpoint(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert "application/manifest+json" in response["Content-Type"]
    manifest = json.loads(response.content.decode("utf-8"))
    assert manifest["name"] == "Gustul Cărților"
    assert manifest["start_url"] == "/copil/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert len(manifest["icons"]) >= 2


def test_service_worker_endpoint(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "application/javascript" in response["Content-Type"]
    assert response.get("Service-Worker-Allowed") == "/"
    assert "no-cache" in response.get("Cache-Control", "")
    content = response.content.decode("utf-8")
    assert "gustul-cartilor-static-" in content
    # Ensure cache cleanup is scoped to gustul-cartilor only
    assert "startsWith(CACHE_PREFIX)" in content
    # Ensure offline route and assets are precached
    assert "/offline/" in content
    assert "/static/js/child.js" in content


def test_offline_view_no_private_data(client):
    response = client.get("/offline/")
    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    content = response.content.decode("utf-8")
    assert "Nu am internet acum" in content
    # Verify no private data leaked in offline view
    for forbidden in ["email", "csrfmiddlewaretoken", "guardian", "child_id", "password"]:
        assert forbidden not in content.lower()


def test_pwa_accessible_in_child_mode(child_session):
    """Critical regression: in real child mode, middleware must allow manifest, sw, offline."""
    client, guardian, child = child_session

    resp_manifest = client.get("/manifest.webmanifest")
    assert resp_manifest.status_code == 200
    assert "application/manifest+json" in resp_manifest["Content-Type"]

    resp_sw = client.get("/sw.js")
    assert resp_sw.status_code == 200
    assert "application/javascript" in resp_sw["Content-Type"]
    assert resp_sw.get("Service-Worker-Allowed") == "/"

    resp_offline = client.get("/offline/")
    assert resp_offline.status_code == 200
    assert "text/html" in resp_offline["Content-Type"]


def test_pwa_fails_closed_when_child_is_invalid(child_session):
    """When active child is tampered with or deleted, ChildModeMiddleware fails closed to pin gate."""
    client, guardian, child = child_session

    session = client.session
    session["active_child"] = "00000000-0000-0000-0000-000000000000"
    session.save()

    response = client.get("/manifest.webmanifest")
    assert response.status_code == 302
    assert response["Location"] == "/parinte/"


def test_icon_dimensions_verified():
    """Ensure icons in staticfiles have exact expected dimensions 192x192 and 512x512."""
    def get_png_dimensions(path):
        with open(path, "rb") as f:
            data = f.read(24)
            assert data[:8] == b"\x89PNG\r\n\x1a\n", "Not a valid PNG file"
            w, h = struct.unpack(">LL", data[16:24])
            return w, h

    icon_192 = Path(settings.BASE_DIR) / "static" / "img" / "icons" / "icon-192.png"
    icon_512 = Path(settings.BASE_DIR) / "static" / "img" / "icons" / "icon-512.png"

    assert get_png_dimensions(icon_192) == (192, 192)
    assert get_png_dimensions(icon_512) == (512, 512)


def test_precache_assets_all_resolve_and_exist():
    # Verify every static asset in the SW precache list is resolvable by Django finders and non-empty
    static_assets = [
        "css/child.css",
        "js/child.js",
        "js/htmx.min.js",
        "img/icons/icon-192.png",
        "img/icons/icon-512.png",
        "img/mascot/mascot-happy.svg",
        "img/mascot/mascot-cheer.svg",
        "img/mascot/mascot-think.svg",
        "img/mascot/mascot-oops.svg",
        "img/avatars/fox.svg",
        "img/avatars/owl.svg",
        "img/avatars/cat.svg",
        "img/avatars/bear.svg",
        "img/avatars/rabbit.svg",
        "img/avatars/hedgehog.svg",
        "img/avatars/squirrel.svg",
        "img/avatars/turtle.svg",
    ]
    for rel_path in static_assets:
        found_path = finders.find(rel_path)
        assert found_path is not None, f"Static asset missing from staticfiles finders: {rel_path}"
        p = Path(found_path)
        assert p.is_file(), f"Asset path is not a file: {found_path}"
        assert p.stat().st_size > 0, f"Asset is empty (0 bytes): {found_path}"
