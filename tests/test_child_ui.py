import importlib
import pytest
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import Client, override_settings
from django.urls import clear_url_caches

from apps.core.viewmodels import BookVM, ChildVM, GrantVM, MascotLine, ShelfEntryVM, StatsVM


@pytest.fixture
def preview_client(client):
    import config.urls

    with override_settings(DEBUG=True):
        importlib.reload(config.urls)
        clear_url_caches()
        yield client

    with override_settings(DEBUG=False):
        importlib.reload(config.urls)
        clear_url_caches()


def test_preview_child_base_has_child_js_and_toast(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/home.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "child.js" in html
    assert 'id="child-toast"' in html
    assert 'role="status"' in html or 'role="alert"' in html


def test_preview_child_home(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/home.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Mia" in html
    assert "fox.svg" in html
    assert "Capra cu trei iezi" in html
    assert "29%" in html
    # Ensure maximum 4 primary navigation items (FR-030)
    assert "/raft/" in html
    assert "/carti/" in html
    assert "/realizari/" in html
    assert "/clubul-meu/" in html
    # Safety: link to adult PIN gate
    assert "/parinte/" in html


def test_preview_child_shelf_entry(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/shelf_entry.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Capra cu trei iezi" in html
    assert "Ion Creangă" in html
    assert "width: 29%;" in html
    assert "request_id" in html
    assert "Am citit până aici" in html
    assert "Am terminat cartea!" in html


def test_preview_child_progress_partial(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/_progress.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "width: 29%;" in html
    assert 'name="page"' in html
    assert 'value="35"' in html
    assert "mascot-cheer.svg" in html or "mascot" in html


def test_preview_child_catalog(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/catalog.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Capra cu trei iezi" in html
    assert "Alege o carte" in html
    assert "Pe raftul tău" in html


def test_preview_child_book_detail_when_on_shelf(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/book_detail.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Capra cu trei iezi" in html
    assert "Ion Creangă" in html
    assert "120" in html
    assert "deja pe raftul tău" in html
    assert "Deschide cartea" in html


def test_child_book_detail_add_to_shelf_form():
    book = BookVM(
        public_id=UUID(int=1), title="Capra cu trei iezi", author="Ion Creangă", page_count=120,
        cover_color="#F4A261", cover_emoji="🐐", genre="fairy_tale", age_band="7-8",
    )
    context = {
        "book": book,
        "shelf_book_ids": set(),
        "entry": None,
    }
    rendered = render_to_string("child/book_detail.html", context)
    # Integration with Alice's PR #21: clean POST form with PRG redirect (no invalid hx-swap)
    assert f'action="/carti/{book.public_id}/adauga/"' in rendered
    assert 'method="post"' in rendered
    assert "Pune pe raftul meu" in rendered


def test_preview_child_shelf(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/shelf.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Raftul meu" in html
    assert "Capra cu trei iezi" in html
    assert "29%" in html


def test_preview_child_achievements(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/achievements.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Trofeele mele" in html
    assert "Prima carte" in html
    assert "Cititor de Club" in html
    assert "Insigna asta e pentru membrii clubului" in html


def test_preview_child_club_corner(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/club_corner.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Clubul de Lectură" in html
    assert "Seară de povești" in html
    # Strict safety check: no external http links and no user chats
    assert "http://" not in html
    assert "https://" not in html
    assert "<textarea" not in html


def test_preview_child_pin_gate(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/pin_gate.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Zonă для părinți" in html or "Zonă pentru părinți" in html
    assert 'name="pin"' in html
    assert 'action="/parinte/"' in html
    assert "/cont/iesire/" in html
    assert "Am uitat PIN-ul" in html


def test_preview_child_offline(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/offline.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Nu am internet acum" in html
    assert "mascot-oops.svg" in html


def test_progress_partial_finished_state():
    book = BookVM(
        public_id=UUID(int=1), title="Capra cu trei iezi", author="Ion Creangă", page_count=120,
        cover_color="#F4A261", cover_emoji="🐐", genre="fairy_tale", age_band="7-8",
    )
    finished_entry = ShelfEntryVM(
        public_id=UUID(int=2), book=book, current_page=120, page_count=120, percent=100, status="finished"
    )
    context = {
        "entry": finished_entry,
        "request_id": UUID(int=9),
        "mascot": MascotLine(key="book_finished", text="Ai terminat cartea! Ce aventură!", mood="cheer"),
        "new_grants": [],
        "errors": [],
    }
    rendered = render_to_string("child/_progress.html", context)
    assert "Cartea este terminată!" in rendered
    assert "width: 100%;" in rendered
    # Page input should not be displayed when finished
    assert 'name="page"' not in rendered


def test_progress_partial_validation_error():
    book = BookVM(
        public_id=UUID(int=1), title="Capra cu trei iezi", author="Ion Creangă", page_count=120,
        cover_color="#F4A261", cover_emoji="🐐", genre="fairy_tale", age_band="7-8",
    )
    entry = ShelfEntryVM(
        public_id=UUID(int=2), book=book, current_page=35, page_count=120, percent=29, status="reading"
    )
    context = {
        "entry": entry,
        "request_id": UUID(int=9),
        "mascot": MascotLine(key="error", text="Hmm, verifică numărul paginii.", mood="oops"),
        "new_grants": [],
        "errors": ["Numărul paginii nu poate fi mai mare decât numărul total de pagini."],
    }
    rendered = render_to_string("child/_progress.html", context)
    assert "Numărul paginii nu poate fi mai mare" in rendered
    assert "Hmm, verifică numărul paginii." in rendered
    # Old saved page remains 35, not false save
    assert 'value="35"' in rendered


def test_child_js_contracts():
    found_js = finders.find("js/child.js")
    assert found_js is not None
    content = Path(found_js).read_text(encoding="utf-8")

    # Double registration guard
    assert "__GUSTUL_CHILD_HTMX_INITIALIZED" in content

    # 422 beforeSwap rule (only 422 swapped)
    assert "status === 422" in content
    assert "evt.detail.shouldSwap = true" in content
    assert "evt.detail.isError = false" in content

    # 401 redirect rule
    assert "status === 401" in content
    assert "HX-Redirect" in content

    # Network / server error toast (Nu s-a salvat)
    assert "htmx:sendError" in content
    assert "Nu s-a salvat — nu ai conexiune la internet." in content
    assert "Nu s-a salvat — baza de date este ocupată." in content

    # HX-Trigger saved confirmation
    assert '"saved"' in content
    assert "Salvat cu succes! ✓" in content


import shutil
import subprocess
import sys
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import Account, ChildProfile, Reader
from apps.club.models import Achievement, AchievementGrant
from apps.library.models import Book, ShelfEntry


def test_child_home_reverse():
    assert reverse("child_home") == "/copil/"


@pytest.fixture
def family_setup(db):
    guardian = Account.objects.create_user(email="guardian_child_home@test.local", password="password123")
    guardian.pin_hash = "valid_pin_hash"
    guardian.save()

    child = ChildProfile.objects.create(
        guardian=guardian,
        nickname="Matei",
        avatar="fox",
        age_band="7-8",
    )
    reader = Reader.objects.create(account=None, child=child, kind=Reader.CHILD)
    return guardian, child, reader


def test_child_home_anonymous_redirects_to_login(client):
    response = client.get("/copil/")
    assert response.status_code == 302
    assert "/cont/intrare/" in response["Location"]

    # HTMX request gets 401 with HX-Redirect
    htmx_resp = client.get("/copil/", HTTP_HX_REQUEST="true")
    assert htmx_resp.status_code == 401
    assert "/cont/intrare/" in htmx_resp["HX-Redirect"]


def test_child_home_adult_mode_forbidden(client, family_setup):
    guardian, child, reader = family_setup
    client.force_login(guardian)
    # Session has no child mode
    response = client.get("/copil/")
    assert response.status_code == 403


def test_child_home_authenticated_child_success_empty_shelf(client, family_setup):
    guardian, child, reader = family_setup
    client.force_login(guardian)
    session = client.session
    session["mode"] = "child"
    session["active_child"] = str(child.public_id)
    session.save()

    response = client.get("/copil/")
    assert response.status_code == 200
    assert "private, no-store" in response["Cache-Control"]
    html = response.content.decode("utf-8")
    assert "Matei" in html
    assert "fox.svg" in html
    assert "Nicio carte pe raft încă" in html
    assert "Alege o carte" in html


def test_child_home_shows_current_book_and_deterministic_order(client, family_setup):
    guardian, child, reader = family_setup
    book1 = Book.objects.create(
        title="Amintiri din copilărie",
        author="Ion Creangă",
        page_count=100,
        age_band="7-8",
        genre="story",
        cover_color="#3B82F6",
        cover_emoji="📘",
    )
    book2 = Book.objects.create(
        title="Povești",
        author="Ion Creangă",
        page_count=80,
        age_band="7-8",
        genre="fairy_tale",
        cover_color="#F59E0B",
        cover_emoji="📙",
    )

    # First entry finished
    ShelfEntry.objects.create(
        reader=reader,
        book=book1,
        current_page=100,
        status="finished",
        finished_at=timezone.now(),
    )
    # Second entry in progress ("reading")
    ShelfEntry.objects.create(
        reader=reader,
        book=book2,
        current_page=20,
        status="reading",
    )

    client.force_login(guardian)
    session = client.session
    session["mode"] = "child"
    session["active_child"] = str(child.public_id)
    session.save()

    response = client.get("/copil/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    # "reading" book must take precedence over "finished"
    assert "Povești" in html
    assert "20 din 80" in html
    assert "25%" in html
    assert "Continuă lectura" in html


def test_child_home_isolation_between_families(client, family_setup):
    guardian1, child1, reader1 = family_setup

    # Create second family
    guardian2 = Account.objects.create_user(email="other_guardian@test.local", password="password123")
    child2 = ChildProfile.objects.create(
        guardian=guardian2,
        nickname="Ana",
        avatar="owl",
        age_band="9-11",
    )
    reader2 = Reader.objects.create(account=None, child=child2, kind=Reader.CHILD)

    client.force_login(guardian2)
    session = client.session
    session["mode"] = "child"
    session["active_child"] = str(child2.public_id)
    session.save()

    response = client.get("/copil/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Ana" in html
    assert "owl.svg" in html
    assert "Matei" not in html


def test_child_home_invalid_active_child_fails_closed(client, family_setup):
    guardian, child, reader = family_setup
    client.force_login(guardian)
    session = client.session
    session["mode"] = "child"
    # Tampered or nonexistent child ID
    session["active_child"] = "00000000-0000-0000-0000-000000000000"
    session.save()

    response = client.get("/copil/")
    # Blocked by ChildModeMiddleware -> redirect to PIN gate
    assert response.status_code == 302
    assert response["Location"] == "/parinte/"


def test_progress_forms_plain_post_action_fallback():
    """Verify both progress and finish forms have matching action and hx-post attributes."""
    book = BookVM(
        public_id=UUID(int=1),
        title="Capra cu trei iezi",
        author="Ion Creangă",
        page_count=120,
        cover_color="#F4A261",
        cover_emoji="🐐",
        genre="fairy_tale",
        age_band="7-8",
    )
    entry = ShelfEntryVM(
        public_id=UUID(int=42),
        book=book,
        current_page=35,
        page_count=120,
        percent=29,
        status="reading",
    )
    context = {
        "entry": entry,
        "request_id": UUID(int=99),
        "mascot": MascotLine(key="welcome", text="Salut!", mood="happy"),
        "new_grants": [],
        "errors": [],
    }
    rendered = render_to_string("child/_progress.html", context)

    # 1. Progress form: action must match hx-post for non-JS / plain POST fallback
    expected_prog_url = f"/raft/{entry.public_id}/progres/"
    assert f'action="{expected_prog_url}"' in rendered
    assert f'hx-post="{expected_prog_url}"' in rendered
    assert 'method="post"' in rendered
    assert 'name="request_id"' in rendered
    assert 'name="page"' in rendered
    assert 'min="0"' in rendered
    assert f'max="{entry.page_count}"' in rendered

    # 2. Finish form: action must match hx-post
    expected_term_url = f"/raft/{entry.public_id}/terminat/"
    assert f'action="{expected_term_url}"' in rendered
    assert f'hx-post="{expected_term_url}"' in rendered


def test_node_child_js_runner():
    """Executes Node test harness for static/js/child.js if node is installed."""
    node_path = shutil.which("node")
    if not node_path:
        pytest.skip("Node.js not installed on system")
    test_file = Path(settings.BASE_DIR) / "tests" / "test_child_js.js"
    res = subprocess.run([node_path, str(test_file)], capture_output=True, text=True)
    assert res.returncode == 0, f"Node.js tests failed:\n{res.stdout}\n{res.stderr}"
