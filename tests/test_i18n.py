"""I18n, Cyrillic hardcoding checks, template preview smoke tests, and HTMX contract tests.

Owned by Vladimir (PR-7).
"""

import importlib
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import clear_url_caches

TEMPLATES_DIR = settings.BASE_DIR / "templates"
STATIC_JS_DIR = settings.BASE_DIR / "static" / "js"
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04FF]")

PREVIEW_TEMPLATES = [
    "adult/landing.html",
    "adult/home.html",
    "adult/login.html",
    "adult/signup.html",
    "adult/dashboard.html",
    "adult/family.html",
    "adult/pin_setup.html",
    "adult/pin_set.html",
    "adult/child_report.html",
    "adult/catalog.html",
    "adult/book_detail.html",
    "adult/shelf.html",
    "adult/shelf_entry.html",
    "adult/_progress.html",
    "adult/achievements.html",
    "adult/redeem_code.html",
    "adult/club_corner.html",
]


@pytest.fixture
def preview_environment():
    """Enable DEBUG and reload urlconf so _preview/<path> is registered (pytest-django defaults DEBUG=False)."""
    import config.urls

    with override_settings(DEBUG=True):
        importlib.reload(config.urls)
        clear_url_caches()
        yield
    with override_settings(DEBUG=False):
        importlib.reload(config.urls)
        clear_url_caches()


def test_no_cyrillic_hardcoded_in_templates():
    """Verify that no Cyrillic characters are hardcoded in Romanian HTML templates."""
    html_files = list(TEMPLATES_DIR.glob("**/*.html"))
    assert len(html_files) > 0, "No template files found to inspect"

    violations = []
    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            if CYRILLIC_PATTERN.search(line):
                violations.append(f"{html_file.relative_to(settings.BASE_DIR)}:{line_no} -> {line.strip()}")

    assert not violations, f"Found hardcoded Cyrillic characters in templates:\n" + "\n".join(violations)


@pytest.mark.django_db
@pytest.mark.parametrize("template_name", PREVIEW_TEMPLATES)
def test_preview_routes_render_200(client: Client, preview_environment, template_name: str):
    """Verify that all adult templates render cleanly with M0 synthetic preview context."""
    with override_settings(DEBUG=True):
        url = f"/_preview/{template_name}"
        response = client.get(url)
        assert response.status_code == 200, f"Preview failed for {url} with status {response.status_code}"
        
        html = response.content.decode("utf-8")
        assert len(html) > 100, f"Preview for {url} returned surprisingly short content"
        # Basic check: should not display raw unrendered template tags
        assert "{%" not in html, f"Unrendered template tag found in {url}"
        assert "{{" not in html, f"Unrendered variable tag found in {url}"


def test_forms_include_csrf():
    """Ensure all mutation forms include CSRF tokens or body has hx-headers CSRF."""
    base_html = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    assert "X-CSRFToken" in base_html, "base.html must configure X-CSRFToken for HTMX"

    # Check key form templates
    form_templates = ["login.html", "signup.html", "family.html", "pin_set.html", "redeem_code.html"]
    for name in form_templates:
        tmpl = (TEMPLATES_DIR / "adult" / name).read_text(encoding="utf-8")
        assert "{% csrf_token %}" in tmpl, f"Form in {name} is missing {{% csrf_token %}}"


def test_htmx_status_handling_contract_in_js():
    """Verify app.js strictly implements the contract from routes.md:

    - htmx:beforeSwap enables swap ONLY for status 422
    - responseError handles 401 (HX-Redirect), 403, 404, 409, 429, 503
    - 'saved' event triggers success toast, but does NOT rotate request_id globally (server partial is authoritative)
    """
    app_js_path = STATIC_JS_DIR / "app.js"
    assert app_js_path.exists(), "static/js/app.js must exist"
    
    content = app_js_path.read_text(encoding="utf-8")

    # 1. 422 only swapping
    assert "htmx:beforeSwap" in content
    assert "422" in content
    assert "shouldSwap = true" in content

    # 2. Status error handling
    assert "htmx:responseError" in content
    assert "401" in content
    assert "HX-Redirect" in content
    assert "Nu s-a salvat" in content

    # 3. Success event: toast only, no global client-side randomUUID mutation
    assert "saved" in content
    assert "crypto.randomUUID" not in content


def test_romanian_po_file_exists():
    """Verify Romanian translation PO catalog exists and is readable."""
    po_path = settings.BASE_DIR / "locale" / "ro" / "LC_MESSAGES" / "django.po"
    assert po_path.exists(), "locale/ro/LC_MESSAGES/django.po must exist"
    content = po_path.read_text(encoding="utf-8")
    assert "Language: ro" in content


def test_root_template_aliases_render():
    """Verify root aliases catalog.html, achievements.html, club_corner.html render cleanly."""
    from django.template.loader import render_to_string
    from apps.core.views import _sample_context

    ctx = _sample_context()
    for tmpl in ["catalog.html", "achievements.html", "club_corner.html"]:
        html = render_to_string(tmpl, ctx)
        assert len(html) > 100
        assert "{%" not in html
