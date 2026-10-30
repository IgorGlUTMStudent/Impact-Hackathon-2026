"""Regression tests for the issue #34 production deployment guard: prod must run on persistent PostgreSQL.

The probe imports config.settings.prod in a fresh interpreter. It deliberately does NOT import
config.wsgi: instantiating the WSGI app populates the app registry, which needs the psycopg driver
for a PostgreSQL ENGINE, and psycopg is only installed on a Postgres host (optional extra). The
settings module itself is what the guard lives in. Explicit empty DJANGO_* / DATABASE_URL values mean
a developer's local .env cannot change the result (base.py only fills unset variables).
"""

import json
import os
import subprocess
import sys

import pytest
from django.conf import settings

PROBE = (
    "import json; import config.settings.prod as s; "
    "print(json.dumps({'debug': s.DEBUG, 'engine': s.DATABASES['default']['ENGINE'], "
    "'atomic_requests': s.DATABASES['default']['ATOMIC_REQUESTS'], "
    "'session_secure': s.SESSION_COOKIE_SECURE, 'csrf_secure': s.CSRF_COOKIE_SECURE, "
    "'ssl_redirect': s.SECURE_SSL_REDIRECT, 'hosts': s.ALLOWED_HOSTS, "
    "'csrf_origins': s.CSRF_TRUSTED_ORIGINS}))"
)

SECRET = "synthetic-test-key-" + "x" * 40
POSTGRES_URL = "postgres://synthetic:synthetic@db.internal:5432/gustul"


def run_prod_probe(**env_overrides):
    """Import config.settings.prod in a fresh interpreter with a controlled environment."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DJANGO_SECRET_KEY": SECRET,
        "DJANGO_ALLOWED_HOSTS": "demo.example.org",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "",
        "DATABASE_URL": "",
    }
    # Windows needs these to bootstrap the interpreter itself; none of them influence Django settings.
    for name in ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC"):
        if os.environ.get(name):
            env[name] = os.environ[name]
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", PROBE], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=120
    )


def test_prod_without_database_url_fails_closed():
    result = run_prod_probe()
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr and "DATABASE_URL" in result.stderr
    assert not result.stdout.strip()  # never started on the SQLite fallback


def test_prod_refuses_empty_but_present_database_url():
    # dj_database_url.config() returns {} for an empty-but-set variable; the guard must win first.
    result = run_prod_probe(DATABASE_URL="")
    assert result.returncode != 0
    assert "Set DATABASE_URL" in result.stderr


def test_prod_refuses_sqlite_database_url():
    result = run_prod_probe(DATABASE_URL="sqlite:///tmp/ephemeral.sqlite3")
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr and "SQLite" in result.stderr
    assert not result.stdout.strip()


def test_prod_uses_postgres_from_database_url():
    result = run_prod_probe(DATABASE_URL=POSTGRES_URL)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "debug": False,
        "engine": "django.db.backends.postgresql",
        "atomic_requests": False,
        "session_secure": True,
        "csrf_secure": True,
        "ssl_redirect": True,
        "hosts": ["demo.example.org"],
        "csrf_origins": [],
    }


def test_prod_appends_render_external_host():
    result = run_prod_probe(
        DATABASE_URL=POSTGRES_URL,
        RENDER_EXTERNAL_HOSTNAME="gustul-cartilor.onrender.com",
        RENDER_EXTERNAL_URL="https://gustul-cartilor.onrender.com",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["hosts"] == ["demo.example.org", "gustul-cartilor.onrender.com"]
    assert data["csrf_origins"] == ["https://gustul-cartilor.onrender.com"]
    assert data["session_secure"] and data["ssl_redirect"]


def test_dev_settings_keep_sqlite_default(monkeypatch):
    """The guard is prod-only; dev/test SQLite behaviour must not change."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


@pytest.mark.parametrize(
    ("blanked", "database_url"),
    [("DATABASE_URL", ""), ("DJANGO_SECRET_KEY", POSTGRES_URL)],
)
def test_prod_guard_names_the_missing_variable(blanked, database_url):
    env = {"DATABASE_URL": database_url, blanked: ""}
    result = run_prod_probe(**env)
    assert result.returncode != 0
    assert blanked in result.stderr
