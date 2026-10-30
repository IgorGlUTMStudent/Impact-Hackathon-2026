"""Integration tests for Adult UX, real accounts backend (PR #26), templates, and contracts.

Owned by Vladimir (PR-7).
"""

import re
from datetime import datetime, timezone
from uuid import UUID

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client

from apps.accounts.models import AGE_BANDS as ACCOUNTS_AGE_BANDS, ChildProfile
from apps.core.viewmodels import BookVM, ChildVM, GrantVM, ShelfEntryVM, StatsVM
from apps.library.models import AGE_BANDS as LIBRARY_AGE_BANDS, GENRES as LIBRARY_GENRES

User = get_user_model()
TEMPLATES_DIR = settings.BASE_DIR / "templates"


# ==============================================================================
# 1. Option sets strictly match models
# ==============================================================================

def test_family_age_bands_match_model():
    """Verify templates/adult/family.html offers all and only valid AGE_BANDS."""
    family_html = (TEMPLATES_DIR / "adult" / "family.html").read_text(encoding="utf-8")
    select_match = re.search(r'<select[^>]*id=["\']id_age_band["\'][^>]*>(.*?)</select>', family_html, re.DOTALL)
    assert select_match is not None, "id_age_band select element must exist in family.html"

    option_values = {opt for opt in re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', select_match.group(1)) if opt}
    model_age_bands = {code for code, _ in ACCOUNTS_AGE_BANDS}

    assert option_values == model_age_bands, (
        f"family.html age bands {option_values} do not match model {model_age_bands}"
    )


def test_catalog_age_bands_and_genres_match_models():
    """Verify templates/adult/catalog.html filter options strictly match model definitions."""
    catalog_html = (TEMPLATES_DIR / "adult" / "catalog.html").read_text(encoding="utf-8")

    # Age bands filter
    age_select = re.search(r'<select[^>]*id=["\']filter-age["\'][^>]*>(.*?)</select>', catalog_html, re.DOTALL)
    assert age_select is not None, "filter-age select element must exist in catalog.html"
    age_values = {opt for opt in re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', age_select.group(1)) if opt}
    expected_ages = {code for code, _ in LIBRARY_AGE_BANDS}
    assert age_values == expected_ages, f"catalog.html age bands {age_values} != {expected_ages}"

    # Genre filter
    genre_select = re.search(r'<select[^>]*id=["\']filter-genre["\'][^>]*>(.*?)</select>', catalog_html, re.DOTALL)
    assert genre_select is not None, "filter-genre select element must exist in catalog.html"
    genre_values = {opt for opt in re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', genre_select.group(1)) if opt}
    expected_genres = {code for code, _ in LIBRARY_GENRES}
    assert genre_values == expected_genres, f"catalog.html genres {genre_values} != {expected_genres}"


# ==============================================================================
# 2. Real Auth Backend Integration (PR #26 in main)
# ==============================================================================

@pytest.mark.django_db
def test_signup_real_backend_flow(client: Client):
    """Verify signup renders adult template with real form and redirects on valid POST."""
    # 1. GET page
    response = client.get("/cont/inregistrare/")
    assert response.status_code == 200
    assert "Creează cont de părinte" in response.content.decode("utf-8")
    assert "csrfmiddlewaretoken" in response.content.decode("utf-8")

    # 2. Invalid POST (empty) -> 422
    response = client.post("/cont/inregistrare/", {})
    assert response.status_code == 422
    assert "form" in response.context

    # 3. Valid POST -> 302 redirect
    response = client.post("/cont/inregistrare/", {
        "email": "ana@familie.ro",
        "display_name": "Ana Popescu",
        "password": "Password12345!",
    })
    assert response.status_code == 302
    assert response["Location"] == settings.LOGIN_REDIRECT_URL
    assert User.objects.filter(email="ana@familie.ro").exists()


@pytest.mark.django_db
def test_login_real_backend_flow(client: Client):
    """Verify login renders adult template, handles 422 on bad credentials, and 302 on success."""
    User.objects.create_user(email="dan@familie.ro", password="Password12345!", display_name="Dan")

    # 1. GET
    response = client.get("/cont/intrare/")
    assert response.status_code == 200
    assert "Conectare părinte" in response.content.decode("utf-8")

    # 2. Invalid credentials -> 422
    response = client.post("/cont/intrare/", {
        "username": "dan@familie.ro",
        "password": "WrongPassword",
    })
    assert response.status_code == 422
    assert "Email sau parolă greșită" in response.content.decode("utf-8")

    # 3. Valid credentials -> 302
    response = client.post("/cont/intrare/", {
        "username": "dan@familie.ro",
        "password": "Password12345!",
    })
    assert response.status_code == 302
    assert response["Location"] == settings.LOGIN_REDIRECT_URL


@pytest.mark.django_db
def test_family_real_backend_flow(client: Client):
    """Verify /familie/ integration: child creation, age_band validation, and rename."""
    user = User.objects.create_user(email="parinte@familie.ro", password="Password12345!", display_name="Părinte")
    client.force_login(user)

    # 1. GET family page
    response = client.get("/familie/")
    assert response.status_code == 200
    assert "Familia mea" in response.content.decode("utf-8")

    # 2. Invalid age_band -> 422, no child created
    response = client.post("/familie/", {
        "nickname": "CopilTest",
        "age_band": "3-5",  # Not in models.AGE_BANDS
        "avatar": "fox",
    })
    assert response.status_code == 422
    assert user.children.count() == 0

    # 3. Valid creation -> 302, child created
    response = client.post("/familie/", {
        "nickname": "Radu",
        "age_band": "9-11",
        "avatar": "fox",
    })
    assert response.status_code == 302
    assert user.children.count() == 1
    child = user.children.first()
    assert child.nickname == "Radu"
    assert child.age_band == "9-11"

    # 4. Rename child -> 302
    response = client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "Radu-Ion"})
    assert response.status_code == 302
    child.refresh_from_db()
    assert child.nickname == "Radu-Ion"


@pytest.mark.django_db
def test_child_delete_confirm_backend_flow():
    """Verify child deletion requires confirm='1', is present in template, and rejects without confirm."""
    client = Client(enforce_csrf_checks=True)
    user = User.objects.create_user(email="mama@familie.ro", password="Password12345!", display_name="Mama")
    child = ChildProfile.objects.create(guardian=user, nickname="Mihai", age_band="7-8", avatar="bear")
    
    client.force_login(user)

    # 1. Check rendered template has hidden confirm='1'
    response = client.get("/familie/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    delete_form_match = re.search(rf'<form[^>]*action=["\']/familie/{child.public_id}/sterge/["\'][^>]*>(.*?)</form>', content, re.DOTALL)
    assert delete_form_match is not None, "Delete form must be rendered for child"
    assert re.search(r'<input[^>]*name=["\']confirm["\'][^>]*value=["\']1["\']', delete_form_match.group(1)) is not None, (
        "Delete form must contain <input type='hidden' name='confirm' value='1'>"
    )

    # 2. POST without confirm='1' (but with valid CSRF) -> 422 and child not deleted
    csrf_token = response.cookies["csrftoken"].value
    response = client.post(f"/familie/{child.public_id}/sterge/", {"csrfmiddlewaretoken": csrf_token})
    assert response.status_code == 422
    assert ChildProfile.objects.filter(pk=child.pk).exists()

    # 3. POST with confirm='1' -> 302 and child deleted
    response = client.post(f"/familie/{child.public_id}/sterge/", {"csrfmiddlewaretoken": csrf_token, "confirm": "1"})
    assert response.status_code == 302
    assert not ChildProfile.objects.filter(pk=child.pk).exists()


@pytest.mark.django_db
def test_pin_set_real_backend_flow(client: Client):
    """Verify /familie/pin/ rendering and setting PIN with password re-auth."""
    user = User.objects.create_user(email="tata@familie.ro", password="Password12345!", display_name="Tata")
    client.force_login(user)

    # 1. GET pin set page
    response = client.get("/familie/pin/")
    assert response.status_code == 200
    assert "Configurare PIN parental" in response.content.decode("utf-8")

    # 2. Wrong adult password -> 422
    response = client.post("/familie/pin/", {
        "pin": "1234",
        "pin_confirm": "1234",
        "password": "WrongPassword",
    })
    assert response.status_code == 422
    user.refresh_from_db()
    assert not user.pin_hash

    # 3. Valid pin & password -> 302 and pin_hash saved
    response = client.post("/familie/pin/", {
        "pin": "5678",
        "pin_confirm": "5678",
        "password": "Password12345!",
    })
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.pin_hash is not None


@pytest.mark.django_db
def test_child_mode_navigation_and_middleware(client: Client):
    """Verify that in child mode adult views are refused by middleware and nav is sanitized."""
    user = User.objects.create_user(email="parent@test.ro", password="Password12345!", display_name="Parent")
    child = ChildProfile.objects.create(guardian=user, nickname="Ioana", age_band="7-8", avatar="owl")
    client.force_login(user)

    # Set PIN
    client.post("/familie/pin/", {"pin": "1111", "pin_confirm": "1111", "password": "Password12345!"})

    # Activate child mode
    response = client.post(f"/familie/{child.public_id}/mod-copil/")
    assert response.status_code == 302
    assert response["Location"] == "/copil/"

    # Adult route /familie/ is refused with 302 -> /parinte/ (pin_gate)
    response = client.get("/familie/")
    assert response.status_code == 302
    assert "/parinte/" in response["Location"]

    # HTMX request to adult route is refused with 403
    response = client.get("/familie/", HTTP_HX_REQUEST="true")
    assert response.status_code == 403


# ==============================================================================
# 3. Child Report Membership Status (No false active entitlement)
# ==============================================================================

def test_child_report_membership_status_no_false_entitlement():
    """Verify child_report.html does not mark expired/revoked memberships as active."""
    child = ChildVM(public_id=UUID(int=1), nickname="Ana", avatar="fox", age_band="9-11")
    stats = StatsVM(books_on_shelf=1, books_finished=0, pages_total=10, pages_7d=10)

    # 1. No membership
    html = render_to_string("adult/child_report.html", {
        "child": child, "stats": stats, "entries": [], "grants": [], "memberships": [],
        "is_member": False,
    })
    assert "Club inactiv" in html
    assert "Membru Club activ" not in html

    # 2. Expired membership with is_member=False
    expired = [{"status": "expired", "valid_until": datetime(2025, 1, 1, tzinfo=timezone.utc)}]
    html = render_to_string("adult/child_report.html", {
        "child": child, "stats": stats, "entries": [], "grants": [], "memberships": expired,
        "is_member": False,
    })
    assert "Membru Club activ" not in html
    assert "Expirat" in html

    # 3. Active entitlement with is_member=True
    active = [{"status": "active", "valid_until": datetime(2027, 1, 1, tzinfo=timezone.utc)}]
    html = render_to_string("adult/child_report.html", {
        "child": child, "stats": stats, "entries": [], "grants": [], "memberships": active,
        "is_member": True,
    })
    assert "Membru Club activ" in html
    assert "✓ Activ" in html


# ==============================================================================
# 4. Progress Form Page 0 Support
# ==============================================================================

def test_progress_page_zero_support():
    """Verify adult/_progress.html allows page 0 for resetting progress."""
    book = BookVM(UUID(int=1), "Carte", "Autor", 100, "#fff", "📖", "story", "7-8")
    entry = ShelfEntryVM(UUID(int=2), book, current_page=0, page_count=100, percent=0, status="reading")

    html = render_to_string("adult/_progress.html", {
        "entry": entry, "request_id": UUID(int=3), "errors": [], "new_grants": [],
    })
    assert 'min="0"' in html
    assert 'value="0"' in html
    assert "între 0 și 100" in html


# ==============================================================================
# 5. Anonymous Catalog and Book Detail CTAs
# ==============================================================================

def test_anonymous_catalog_and_detail_cta():
    """Verify anonymous visitors see login CTA and no mutation <form action='...adauga/'>."""
    book = BookVM(UUID(int=10), "Basme", "Creangă", 80, "#F4A261", "🐐", "fairy_tale", "7-8")

    # 1. Anonymous catalog view
    html = render_to_string("adult/catalog.html", {
        "books": [book], "filters": {}, "shelf_book_ids": set(),
        "request": type("Request", (), {"user": type("Anon", (), {"is_authenticated": False})(), "GET": {}})(),
    })
    assert "Conectare pentru a adăuga" in html
    assert f"/carti/{book.public_id}/adauga/" not in html

    # 2. Anonymous book detail view
    html = render_to_string("adult/book_detail.html", {
        "book": book, "shelf_book_ids": set(),
        "request": type("Request", (), {"user": type("Anon", (), {"is_authenticated": False})()})(),
    })
    assert "Conectează-te pentru a adăuga pe raft" in html
    assert f"/carti/{book.public_id}/adauga/" not in html
