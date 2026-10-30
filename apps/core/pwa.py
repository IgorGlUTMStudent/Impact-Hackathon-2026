"""PWA views for Gustul Cărților.

Owner: Denis (Antigravity).
Contracts: specs/001-reading-diary-mvp/contracts/routes.md § Route 18.
Provides:
- /manifest.webmanifest: Web App Manifest with correct MIME type
- /sw.js: Service Worker served at root scope with Service-Worker-Allowed: /
- /offline/: Static unauthenticated offline fallback page
"""

from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .mascot import get_mascot_line


_STATIC_DIR = Path(settings.BASE_DIR) / "static"


@require_GET
def manifest_view(request):
    """Serve the Web App Manifest with application/manifest+json MIME type."""
    manifest_path = _STATIC_DIR / "manifest.webmanifest"
    if manifest_path.exists():
        content = manifest_path.read_text(encoding="utf-8")
    else:
        content = "{}"

    response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "public, max-age=86400"
    return response


@require_GET
def service_worker_view(request):
    """Serve the root-scoped service worker with Service-Worker-Allowed: /."""
    sw_path = _STATIC_DIR / "sw.js"
    if sw_path.exists():
        content = sw_path.read_text(encoding="utf-8")
    else:
        content = "// sw missing"

    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    # Crucial for PWA installation: allow the service worker to control all routes from /
    response["Service-Worker-Allowed"] = "/"
    # Always revalidate service worker script
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@require_GET
def offline_view(request):
    """Public unauthenticated offline fallback shell. Never exposes private child/family data."""
    context = {
        "mascot": get_mascot_line("offline"),
    }
    response = render(request, "child/offline.html", context)
    response["Cache-Control"] = "public, max-age=3600"
    return response

