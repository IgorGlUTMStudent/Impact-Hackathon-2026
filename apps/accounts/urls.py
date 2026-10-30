from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

# contracts/routes.md rows 4–9, 16. URL names are part of the child-mode allow-list contract.
urlpatterns = [
    path("cont/inregistrare/", views.signup, name="signup"),
    path("cont/intrare/", views.ThrottledLoginView.as_view(), name="login"),
    path("cont/iesire/", LogoutView.as_view(), name="logout"),  # POST only; ends the whole session
    path("panou/", views.adult_dashboard, name="adult_dashboard"),
    path("familie/", views.family, name="family"),
    path("familie/pin/", views.pin_set, name="pin_set"),
    path("familie/<uuid:child>/", views.child_report, name="child_report"),
    path("familie/<uuid:child>/editeaza/", views.child_rename, name="child_rename"),
    path("familie/<uuid:child>/sterge/", views.child_delete, name="child_delete"),
    path("familie/<uuid:child>/mod-copil/", views.child_mode_start, name="child_mode_start"),
    path("parinte/", views.pin_gate, name="pin_gate"),
]
