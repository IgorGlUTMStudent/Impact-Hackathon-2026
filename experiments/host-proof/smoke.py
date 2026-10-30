"""Isolated synthetic host probe. Not application code or production settings."""
import os
import sys
from pathlib import Path
import dj_database_url

from django.conf import settings

BASE = Path(__file__).resolve().parent
if os.environ.get("RENDER") and not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is required on Render; do not use ephemeral SQLite")
external_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
external_url = os.environ.get("RENDER_EXTERNAL_URL", "")
settings.configure(
    SECRET_KEY=os.environ["DJANGO_SECRET_KEY"],
    DEBUG=False,
    ALLOWED_HOSTS=os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") + ([external_host] if external_host else []),
    ROOT_URLCONF=__name__,
    DATABASES={"default": dj_database_url.config(default=f"sqlite:///{BASE / 'smoke.sqlite3'}")},
    CSRF_TRUSTED_ORIGINS=[x for x in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if x] + ([external_url] if external_url else []),
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions"],
    MIDDLEWARE=["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware"],
    LOGIN_URL="/login/",
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
import django
django.setup()
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.management import execute_from_command_line
from django.core.wsgi import get_wsgi_application
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest
from django.middleware.csrf import get_token
from django.urls import path
from django.views.decorators.http import require_http_methods

def health(request):
    return HttpResponse("ok")

def manifest(request):
    return HttpResponse('{"name":"Host proof","short_name":"Host proof","start_url":"/value/","display":"standalone","icons":[{"src":"/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"/icon-512.png","sizes":"512x512","type":"image/png"}]}', content_type="application/manifest+json")

def icon(request, size):
    if size not in (192, 512):
        return HttpResponse(status=404)
    return HttpResponse((BASE / f"icon-{size}.png").read_bytes(), content_type="image/png")

def service_worker(request):
    return HttpResponse("self.addEventListener('install', e => e.waitUntil(caches.open('host-proof-v1').then(c => c.put('/offline', new Response('Offline: writes unavailable', {headers: {'Content-Type': 'text/plain'}}))))); self.addEventListener('fetch', e => { if (e.request.method === 'GET' && e.request.mode === 'navigate') e.respondWith(fetch(e.request).catch(() => caches.match('/offline'))); });", content_type="application/javascript")

@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user is None:
            return HttpResponse("Invalid login", status=403)
        login(request, user)
        # Redirect to the read page; do not leave the password POST in browser history.
        return HttpResponse(status=303, headers={"Location": "/value/"})
    return HttpResponse(f'<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}"><input name="username"><input name="password" type="password"><button>Login</button></form>')

@login_required
@require_http_methods(["GET", "POST"])
def value(request):
    with connection.cursor() as cursor:
        if request.method == "POST":
            try:
                number = int(request.POST["value"])
                if not 0 <= number <= 1000000:
                    raise ValueError
            except (KeyError, ValueError):
                return HttpResponseBadRequest("Invalid number")
            cursor.execute("UPDATE host_proof_value SET value = %s WHERE id = 1", [number])
            # POST/Redirect/GET: reloading the read page must not re-submit an old value.
            return HttpResponse(status=303, headers={"Location": "/value/"})
        cursor.execute("SELECT value FROM host_proof_value WHERE id = 1")
        number = cursor.fetchone()[0]
    response = HttpResponse(f'<link rel="manifest" href="/manifest.webmanifest"><script>if("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");</script><p>Value: {number}</p><form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}"><input name="value" type="number"><button>Save</button></form>')
    response["Cache-Control"] = "no-store"
    return response

urlpatterns = [path("health/", health), path("login/", sign_in), path("value/", value), path("manifest.webmanifest", manifest), path("sw.js", service_worker), path("icon-<int:size>.png", icon)]
application = get_wsgi_application()

if __name__ == "__main__":
    if sys.argv[1:] == ["init-value"]:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS host_proof_value (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)")
            cursor.execute("INSERT INTO host_proof_value (id, value) VALUES (1, 0) ON CONFLICT (id) DO NOTHING")
        username = os.environ.get("PROOF_USERNAME")
        password = os.environ.get("PROOF_PASSWORD")
        if username and password:
            get_user_model().objects.get_or_create(username=username, defaults={"password": "!"})
            user = get_user_model().objects.get(username=username)
            user.set_password(password)
            user.save(update_fields=["password"])
    else:
        execute_from_command_line(sys.argv)
