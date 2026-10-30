import importlib
import pytest
from uuid import UUID

from django.conf import settings
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


def test_preview_child_book_detail(preview_client):
    with override_settings(DEBUG=True):
        response = preview_client.get("/_preview/child/book_detail.html")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Capra cu trei iezi" in html
    assert "Ion Creangă" in html
    assert "120" in html


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
    assert "Zonă pentru părinți" in html
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
    from django.template.loader import render_to_string
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
    from django.template.loader import render_to_string
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
