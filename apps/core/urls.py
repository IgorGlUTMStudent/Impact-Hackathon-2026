"""Core application URLs (PWA manifest, root service worker, offline fallback, child home).

Owner: Denis (Antigravity).
Contracts:
- specs/001-reading-diary-mvp/contracts/routes.md § Route 1 (/copil/), Route 18 (PWA)
- specs/001-reading-diary-mvp/contracts/authorization.md § CHILD_ALLOWED
"""

from django.urls import path

from . import child_views, pwa

urlpatterns = [
    path("copil/", child_views.child_home, name="child_home"),
    path("manifest.webmanifest", pwa.manifest_view, name="manifest"),
    path("sw.js", pwa.service_worker_view, name="sw"),
    path("offline/", pwa.offline_view, name="offline"),
]
