import importlib

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse

from apps.accounts.models import Account
from apps.club.services import evaluate_achievements
from apps.core.viewmodels import percent


def test_sqlite_uses_immediate_transactions_and_busy_timeout(db):
    assert connection.vendor == "sqlite"
    assert settings.DATABASES["default"]["ATOMIC_REQUESTS"] is False
    connection.ensure_connection()
    assert connection.transaction_mode == "IMMEDIATE"  # Django issues BEGIN IMMEDIATE
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout")
        assert cursor.fetchone()[0] == 5000


def test_healthz_get(client, db):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}
    assert client.post("/healthz/").status_code == 405


def test_admin_requires_login(client, db):
    response = client.get("/admin/")
    assert response.status_code == 302 and "/admin/login/" in response["Location"]


def test_createsuperuser_and_admin_login(client, db, monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "x-strong-pass-1")
    call_command("createsuperuser", interactive=False, email="Boss@Demo.Local", display_name="Boss", verbosity=0)
    boss = Account.objects.get(email="boss@demo.local")
    assert boss.is_staff and boss.is_superuser
    assert client.login(username="BOSS@demo.local", password="x-strong-pass-1")
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/accounts/childprofile/").status_code == 200


@pytest.fixture
def urlconf_built_with_debug():
    """Rebuild config.urls as it is at process start with the given DEBUG (pytest-django forces DEBUG=False)."""
    import config.urls

    def build(debug):
        with override_settings(DEBUG=debug):
            importlib.reload(config.urls)
        clear_url_caches()

    yield build
    build(False)


def test_preview_renders_synthetic_context_when_debug_on(client, tmp_path, urlconf_built_with_debug):
    urlconf_built_with_debug(True)
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "probe.html").write_text("{{ child.nickname }} {{ entry.percent }}%")
    templates = [{**settings.TEMPLATES[0], "DIRS": [tmp_path]}]
    with override_settings(DEBUG=True, TEMPLATES=templates):
        response = client.get("/_preview/child/probe.html")
        assert response.status_code == 200 and response.content.decode() == "Mia 29%"
        assert client.get("/_preview/admin/base.html").status_code == 404
        assert client.get("/_preview/child/does-not-exist.html").status_code == 404


def test_preview_view_refuses_when_debug_off_even_if_routed(client, tmp_path, urlconf_built_with_debug):
    urlconf_built_with_debug(True)  # route present, as in a dev process...
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "probe.html").write_text("ok")
    with override_settings(DEBUG=False, TEMPLATES=[{**settings.TEMPLATES[0], "DIRS": [tmp_path]}]):
        assert client.get("/_preview/child/probe.html").status_code == 404  # ...but the view checks DEBUG too


def test_preview_route_absent_when_built_with_debug_off(urlconf_built_with_debug):
    urlconf_built_with_debug(False)
    with pytest.raises(NoReverseMatch):
        reverse("template_preview", args=["child/home.html"])


def test_prod_settings_are_safe(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-only-" + "k" * 40)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "demo.example.org")
    # Issue #34: prod requires a persistent PostgreSQL and must never fall back to SQLite.
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/gustul")
    base = importlib.reload(importlib.import_module("config.settings.base"))
    prod = importlib.reload(importlib.import_module("config.settings.prod"))
    try:
        assert prod.DEBUG is False
        assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE
        assert prod.ALLOWED_HOSTS == ["demo.example.org"]
        assert prod.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
        assert "transaction_mode" not in prod.DATABASES["default"]
    finally:
        monkeypatch.delenv("DATABASE_URL")
        importlib.reload(base)


def test_prod_settings_require_secret_key(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("DJANGO_SECRET_KEY", "")
    # Keep DATABASE_URL valid so the raised error is the secret-key guard, not the new database guard.
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/gustul")
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(importlib.import_module("config.settings.prod"))


def test_database_url_switches_engine_without_sqlite_options(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/gustul")
    base = importlib.reload(importlib.import_module("config.settings.base"))
    try:
        assert base.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
        assert "transaction_mode" not in base.DATABASES["default"].get("OPTIONS", {})
    finally:
        monkeypatch.delenv("DATABASE_URL")
        importlib.reload(base)


@pytest.mark.django_db
def test_evaluate_achievements_grants_stored_progress_once():
    from apps.accounts.models import Reader
    from apps.club.models import Achievement, AchievementGrant
    from apps.library.models import Book, ShelfEntry

    account = Account.objects.create_user("achievement@demo.local", "synthetic-password")
    reader = Reader.objects.create(kind=Reader.ADULT, account=account)
    achievement = Achievement.objects.create(
        code="pages-100", title="100 pagini", description="Synthetic",
        rule=Achievement.PAGES_TOTAL_GTE, threshold=100, icon="pages",
    )
    book = Book.objects.create(
        title="Synthetic", author="Synthetic", page_count=120, genre="story",
        cover_color="#123456", cover_emoji="📘", source_note="test",
    )
    entry = ShelfEntry.objects.create(reader=reader, book=book, current_page=35)
    assert evaluate_achievements(reader) == []
    entry.current_page = 100
    entry.save()
    grants = evaluate_achievements(reader)
    assert len(grants) == 1
    assert grants[0].achievement == achievement and not grants[0].was_member
    assert evaluate_achievements(reader) == []
    assert AchievementGrant.objects.filter(reader=reader, achievement=achievement).count() == 1


@pytest.mark.parametrize("current, total, expected", [(0, 120, 0), (35, 120, 29), (120, 120, 100), (5, 0, 0)])
def test_percent(current, total, expected):
    assert percent(current, total) == expected
