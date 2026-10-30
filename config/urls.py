from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

# Each app owns its routes in apps/<app>/urls.py (contracts/routes.md); this file only includes them.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", core_views.healthz, name="healthz"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.library.urls")),
    path("", include("apps.club.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    # The view refuses with 404 when DEBUG is off too (defence in depth).
    urlpatterns.append(path("_preview/<path:template_name>", core_views.template_preview, name="template_preview"))
