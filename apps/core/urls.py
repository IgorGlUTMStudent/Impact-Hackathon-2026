"""Core application URLs (PWA manifest, root service worker, offline fallback).

Owner: Denis (Antigravity).
Contracts: specs/001-reading-diary-mvp/contracts/routes.md § Route 18.
"""

from django.urls import path
from . import pwa

urlpatterns = [
    path("manifest.webmanifest", pwa.manifest_view, name="pwa_manifest"),
    path("sw.js", pwa.service_worker_view, name="pwa_sw"),
    path("offline/", pwa.offline_view, name="pwa_offline"),
]
