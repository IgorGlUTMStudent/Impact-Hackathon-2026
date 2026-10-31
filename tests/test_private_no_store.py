"""Private authenticated responses carry an explicit no-store cache policy (issue #47).

Real clients and real child-mode flows only — no authz mocks. Public pages
(catalog, book detail, manifest) keep the existing policy: no blanket no-store.
"""

from uuid import uuid4

import pytest

from apps.library.models import Book, ShelfEntry

from .conftest import HTMX

pytestmark = pytest.mark.django_db


def make_shelf_entry(child):
    book = Book.objects.create(
        public_id=uuid4(), title="Carte raft", author="Autor", page_count=120, cover_color="#fff",
        cover_emoji="📄", genre="fairy_tale", age_band="9-11",
    )
    return ShelfEntry.objects.create(reader=child.reader, book=book, current_page=10, status=ShelfEntry.READING)


def no_store(response):
    return "no-store" in (response.get("Cache-Control") or "")


# --- accounts (owner Арсений) -------------------------------------------------------------------------------------

def test_adult_account_pages_are_no_store(adult_client, child):
    for path in ("/panou/", "/familie/", f"/familie/{child.public_id}/"):
        response = adult_client.get(path)
        assert response.status_code == 200, path
        assert no_store(response), path


def test_family_422_renders_are_no_store(adult_client, child):
    # invalid create + invalid rename re-render pages with the family's child data
    invalid_create = adult_client.post("/familie/", {"nickname": "Mia", "age_band": "", "avatar": "owl"})
    assert invalid_create.status_code == 422 and no_store(invalid_create)
    bad_rename = adult_client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "x"})  # too short
    assert bad_rename.status_code == 422 and no_store(bad_rename)


def test_pin_set_page_is_no_store(adult_client):
    response = adult_client.get("/familie/pin/")
    assert response.status_code == 200 and no_store(response)


# --- library (owner Алиса) -----------------------------------------------------------------------------------------

def test_child_shelf_pages_are_no_store(child_client, child):
    entry = make_shelf_entry(child)
    for path in ("/raft/", f"/raft/{entry.public_id}/"):
        response = child_client.get(path)
        assert response.status_code == 200, path
        assert no_store(response), path


def test_progress_partial_200_and_422_are_no_store_without_saved_trigger(child_client, child):
    entry = make_shelf_entry(child)
    url = f"/raft/{entry.public_id}/progres/"
    saved = child_client.post(url, {"page": 35, "request_id": uuid4()}, **HTMX)
    assert saved.status_code == 200 and no_store(saved)
    assert saved.get("HX-Trigger") == "saved"
    rejected = child_client.post(url, {"page": 9999, "request_id": uuid4()}, **HTMX)
    assert rejected.status_code == 422 and no_store(rejected)
    assert "HX-Trigger" not in rejected  # never a spurious "saved" acknowledgement on errors


# --- policies that must not change ----------------------------------------------------------------------------------

def test_already_protected_pages_stay_protected(child_client):
    assert no_store(child_client.get("/copil/"))  # child home: private, no-store, must-revalidate
    assert no_store(child_client.get("/realizari/"))  # club views: never_cache


def test_public_catalog_keeps_existing_policy(client):
    # no blanket middleware: the public catalog is deliberately not no-store
    response = client.get("/carti/")
    assert response.status_code == 200
    assert "no-store" not in (response.get("Cache-Control") or "")
