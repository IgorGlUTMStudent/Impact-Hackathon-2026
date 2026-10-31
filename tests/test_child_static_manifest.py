"""Issue #56 regression: child-mode pages must render under the production manifest storage.

Production (config/settings/prod.py) serves static files with whitenoise's
CompressedManifestStaticFilesStorage: every ``{% static %}`` argument must be a complete
path that exists in the collectstatic manifest, otherwise the render raises
``ValueError: Missing staticfiles manifest entry`` → HTTP 500. The bug was partial paths
("img/mascot/mascot-") concatenated with template variables after the tag.

These tests are the only ones in the suite that exercise the real production storage:
they override STORAGES, collectstatic into an isolated STATIC_ROOT and assert against
the generated staticfiles.json — no mocking of staticfiles_storage.url.
"""

import json
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.library import services
from apps.library.models import Book

from .conftest import HTMX, PIN, make_child, make_guardian

pytestmark = pytest.mark.django_db

PROD_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MASCOTS = ("happy", "cheer", "think", "oops")
AVATARS = ("fox", "owl", "cat", "bear", "rabbit", "hedgehog", "squirrel", "turtle")


@pytest.fixture
def manifest_static(tmp_path, settings) -> Path:
    """Isolated STATIC_ROOT + prod storage: collectstatic builds the real manifest."""
    settings.DEBUG = False
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    settings.STORAGES = PROD_STORAGES
    static_root = settings.STATIC_ROOT
    call_command("collectstatic", interactive=False, verbosity=0, clear=True)
    return static_root


def manifest_paths(static_root):
    return json.loads((static_root / "staticfiles.json").read_text(encoding="utf-8"))["paths"]


# --- the manifest itself -----------------------------------------------------------------------------------------

def test_manifest_contains_every_mascot_and_avatar(manifest_static):
    paths = manifest_paths(manifest_static)
    for mood in MASCOTS:
        assert f"img/mascot/mascot-{mood}.svg" in paths
    for avatar in AVATARS:
        assert f"img/avatars/{avatar}.svg" in paths


# --- the reported journey: Mod Copil → /copil/ --------------------------------------------------------------------

def test_mod_copil_renders_child_home_with_manifest_urls(adult_client, child, manifest_static):
    book = Book.objects.create(title="Poveste", author="Demo", page_count=120, genre="story")
    services.add_to_shelf(child.reader, book)
    response = adult_client.post(f"/familie/{child.public_id}/mod-copil/")
    assert response.status_code == 302 and response["Location"] == "/copil/"
    response = adult_client.get("/copil/")
    assert response.status_code == 200
    html = response.content.decode()
    paths = manifest_paths(manifest_static)
    # The rendered URLs are exactly the hashed names from the real manifest, not partial paths.
    assert paths["img/mascot/mascot-happy.svg"] in html
    assert paths["img/avatars/fox.svg"] in html
    # Unhashed complete names would mean the URL bypassed the manifest.
    assert '"/static/img/mascot/mascot-happy.svg"' not in html
    assert '"/static/img/avatars/fox.svg"' not in html
    assert response["Cache-Control"] == "private, no-store, must-revalidate"


def test_child_home_empty_shelf_renders_invitation(adult_client, guardian, manifest_static):
    ada = make_child(guardian, nickname="Ada")
    ada.avatar = "owl"
    ada.save(update_fields=["avatar"])
    assert adult_client.post(f"/familie/{ada.public_id}/mod-copil/").status_code == 302
    response = adult_client.get("/copil/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Nicio carte pe raft încă" in html
    assert manifest_paths(manifest_static)["img/avatars/owl.svg"] in html


# --- Înapoi la lectură and the child badge ("Copil" fallback) on the PIN gate --------------------------------------

def test_pin_gate_back_link_returns_to_working_child_home(child_client, manifest_static):
    gate = child_client.get("/parinte/")
    assert gate.status_code == 200
    html = gate.content.decode()
    assert 'href="/copil/"' in html  # "Înapoi la lectură" and the child badge both target /copil/
    assert ">Copil<" in html  # badge fallback text (the gate context has no child profile)
    assert child_client.get("/copil/").status_code == 200  # the link lands on a working page


# --- dynamic mascot moods on the reading flow ----------------------------------------------------------------------

def test_progress_flows_render_dynamic_moods_manifest_safe(child_client, child, manifest_static):
    book = Book.objects.create(title="Poveste", author="Demo", page_count=120, genre="story")
    entry, _ = services.add_to_shelf(child.reader, book)
    paths = manifest_paths(manifest_static)
    url = f"/raft/{entry.public_id}/"
    # welcome → happy
    assert paths["img/mascot/mascot-happy.svg"] in child_client.get(url).content.decode()
    # validation error → oops (HTMX partial render of _progress.html)
    bad = child_client.post(url + "progres/", {"page": "999", "request_id": str(uuid.uuid4())}, **HTMX)
    assert bad.status_code == 422
    assert paths["img/mascot/mascot-oops.svg"] in bad.content.decode()
    # saved progress → happy (again via the HTMX partial)
    saved = child_client.post(url + "progres/", {"page": "50", "request_id": str(uuid.uuid4())}, **HTMX)
    assert saved.status_code == 200
    assert paths["img/mascot/mascot-happy.svg"] in saved.content.decode()
    # finished book → cheer
    done = child_client.post(url + "terminat/", {"request_id": str(uuid.uuid4())}, **HTMX)
    assert done.status_code == 200
    assert paths["img/mascot/mascot-cheer.svg"] in done.content.decode()


# --- authorization matrix around the reports (unchanged by the fix) -------------------------------------------------

def test_adult_reports_open_without_pin_and_child_mode_blocks_them(adult_client, guardian, manifest_static):
    with_book = make_child(guardian, nickname="Dan")
    empty = make_child(guardian, nickname="Ada")
    book = Book.objects.create(title="Poveste", author="Demo", page_count=120, genre="story")
    services.add_to_shelf(with_book.reader, book)
    foreign = make_child(make_guardian("altul@demo.local"))
    # Adult mode: both own reports open without a PIN; foreign profiles stay 404.
    assert adult_client.get(f"/familie/{with_book.public_id}/").status_code == 200
    assert adult_client.get(f"/familie/{empty.public_id}/").status_code == 200
    assert adult_client.get(f"/familie/{foreign.public_id}/").status_code == 404
    # Child mode: the same reports are behind the PIN gate; /copil/ keeps working.
    assert adult_client.post(f"/familie/{with_book.public_id}/mod-copil/").status_code == 302
    assert adult_client.get(f"/familie/{empty.public_id}/")["Location"] == "/parinte/"
    assert adult_client.get("/parinte/").status_code == 200
    assert adult_client.get("/copil/").status_code == 200
    # Wrong PIN stays refused; the correct PIN restores adult mode.
    assert adult_client.post("/parinte/", {"pin": "0000"}).status_code == 422
    unlock = adult_client.post("/parinte/", {"pin": PIN})
    assert unlock.status_code == 302 and unlock["Location"] == "/panou/"
    assert adult_client.get(f"/familie/{with_book.public_id}/").status_code == 200
