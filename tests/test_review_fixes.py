"""Regression tests for the PR #13 security review: WSGI fail-closed, PIN hash and child data in admin."""

import json
import os
import subprocess
import sys

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password

from apps.accounts.models import Account, ChildProfile

# Prints the settings a WSGI server would actually run with.
PROBE = (
    "import json, os, config.wsgi; from django.conf import settings as s; "
    "print(json.dumps({'module': os.environ['DJANGO_SETTINGS_MODULE'], 'debug': s.DEBUG, "
    "'session_secure': s.SESSION_COOKIE_SECURE, 'csrf_secure': s.CSRF_COOKIE_SECURE, "
    "'ssl_redirect': s.SECURE_SSL_REDIRECT, 'hosts': s.ALLOWED_HOSTS}))"
)


def run_wsgi_probe(**env_overrides):
    """Import config.wsgi in a fresh interpreter with a minimal environment.

    DJANGO_SECRET_KEY / DJANGO_ALLOWED_HOSTS are always set explicitly (possibly empty): the .env loader in
    base.py only fills unset variables, so a developer's local .env cannot change the result.
    """
    env = {"PATH": os.environ.get("PATH", ""), "DJANGO_SECRET_KEY": "", "DJANGO_ALLOWED_HOSTS": ""}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", PROBE], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=120
    )


def test_wsgi_without_settings_module_fails_closed_without_secret():
    # Issue #34: prod now also requires DATABASE_URL, so the probe carries a synthetic PostgreSQL URL and
    # the missing-variable guard under test stays the DJANGO_SECRET_KEY one.
    result = run_wsgi_probe(DATABASE_URL="postgres://u:p@localhost:5432/gustul")
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr and "DJANGO_SECRET_KEY" in result.stderr
    assert '"debug": true' not in result.stdout  # never fell back to dev


def test_wsgi_without_settings_module_starts_with_prod():
    result = run_wsgi_probe(
        DJANGO_SECRET_KEY="synthetic-test-key-" + "x" * 40,
        DJANGO_ALLOWED_HOSTS="demo.example.org",
        # A prod start now means a PostgreSQL engine; needs the driver from the postgres extra (CI parity).
        DATABASE_URL="postgres://u:p@localhost:5432/gustul",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "module": "config.settings.prod", "debug": False, "session_secure": True, "csrf_secure": True,
        "ssl_redirect": True, "hosts": ["demo.example.org"],
    }


def test_wsgi_respects_explicit_settings_module():
    result = run_wsgi_probe(DJANGO_SETTINGS_MODULE="config.settings.dev")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["module"] == "config.settings.dev"


def test_manage_py_still_defaults_to_dev():
    env = {"PATH": os.environ.get("PATH", ""), "DJANGO_SECRET_KEY": ""}
    result = subprocess.run(
        [sys.executable, "manage.py", "diffsettings", "--output", "unified"],
        cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "+ DEBUG = True" in result.stdout


@pytest.fixture
def admin_client_superuser(client, db):
    Account.objects.create_superuser("boss@demo.local", "x-strong-pass-1", display_name="Boss")
    client.login(username="boss@demo.local", password="x-strong-pass-1")
    return client


def test_admin_never_renders_pin_hash(admin_client_superuser):
    guardian = Account.objects.create_user("parinte@demo.local", "x-strong-pass-1", display_name="P")
    guardian.pin_hash = make_password("2468")
    guardian.save()

    html = admin_client_superuser.get(f"/admin/accounts/account/{guardian.pk}/change/").content.decode()
    assert "parinte@demo.local" in html  # the page really rendered this account
    assert guardian.pin_hash not in html
    assert guardian.pin_hash.split("$")[2] not in html  # not even the salt
    assert "pin_hash" not in html

    guardian.refresh_from_db()
    assert guardian.pin_hash and guardian.pin_hash.startswith("pbkdf2_sha256$")  # still stored for PR-2


def test_admin_child_profile_shows_nickname_only(admin_client_superuser):
    guardian = Account.objects.create_user("parinte@demo.local", "x-strong-pass-1", display_name="P")
    child = ChildProfile.objects.create(guardian=guardian, nickname="Mia", age_band="9-11", avatar="fox")

    changelist = admin_client_superuser.get("/admin/accounts/childprofile/").content.decode()
    detail = admin_client_superuser.get(f"/admin/accounts/childprofile/{child.pk}/change/").content.decode()
    for html in (changelist, detail):
        assert "Mia" in html
        assert "9–11" not in html  # age band display value
        for hidden in ("age_band", "created_at", "avatar", "guardian"):
            assert f"column-{hidden}" not in html and f"field-{hidden}" not in html
    assert "field-nickname" in detail

    # Still read-only for staff.
    assert admin_client_superuser.get("/admin/accounts/childprofile/add/").status_code == 403
    response = admin_client_superuser.post(f"/admin/accounts/childprofile/{child.pk}/change/", {"nickname": "Hacked"})
    assert response.status_code == 403
    child.refresh_from_db()
    assert child.nickname == "Mia"


def test_readonly_admin_denies_delete_even_for_superuser(admin_client_superuser):
    """All read-only admin classes must deny deletion, including for superusers."""
    from django.contrib import admin
    from django.test import RequestFactory

    from apps.accounts.models import Reader, Throttle
    from apps.club.models import AchievementGrant, ClubMembership, MembershipCode
    from apps.library.models import ProgressEvent, ShelfEntry

    request = RequestFactory().get("/admin/")
    request.user = Account.objects.get(email="boss@demo.local")
    assert request.user.is_superuser

    readonly = (ChildProfile, Reader, Throttle, ShelfEntry, ProgressEvent, AchievementGrant)
    for model in readonly:
        model_admin = admin.site._registry[model]
        assert not model_admin.has_add_permission(request), model.__name__
        assert not model_admin.has_change_permission(request), model.__name__

    # PR-5 deliberately permits controlled club issuance/activation, not editing.
    for model in (ClubMembership, MembershipCode):
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request), model.__name__
        assert not model_admin.has_change_permission(request, model()), model.__name__

    for model in (*readonly, ClubMembership, MembershipCode):
        model_admin = admin.site._registry[model]
        assert not model_admin.has_delete_permission(request), model.__name__
        assert "delete_selected" not in model_admin.get_actions(request), model.__name__


def test_readonly_admin_rejects_child_delete_and_bulk_delete(admin_client_superuser):
    """The superuser delete URL and crafted bulk action must not delete child data."""
    from apps.accounts.models import Reader
    from apps.library.models import Book, ShelfEntry

    guardian = Account.objects.create_user("parinte@demo.local", "x-strong-pass-1", display_name="P")
    child = ChildProfile.objects.create(guardian=guardian, nickname="Mia", age_band="9-11", avatar="fox")
    reader = Reader.objects.create(kind=Reader.CHILD, child=child)
    book = Book.objects.create(
        title="Synthetic", author="Synthetic", page_count=120, genre="story",
        cover_color="#123456", cover_emoji="📘", source_note="test",
    )
    entry = ShelfEntry.objects.create(reader=reader, book=book)
    url = f"/admin/accounts/childprofile/{child.pk}/delete/"

    assert admin_client_superuser.get(url).status_code == 403
    assert admin_client_superuser.post(url, {"post": "yes"}).status_code == 403

    # A forged action POST cannot bypass the absence of the bulk delete action.
    response = admin_client_superuser.post(
        "/admin/accounts/childprofile/",
        {"action": "delete_selected", "_selected_action": [str(child.pk)], "index": "0"},
    )
    assert response.status_code in (200, 302)
    assert ChildProfile.objects.filter(pk=child.pk).exists()
    assert Reader.objects.filter(pk=reader.pk).exists()
    assert ShelfEntry.objects.filter(pk=entry.pk).exists()
