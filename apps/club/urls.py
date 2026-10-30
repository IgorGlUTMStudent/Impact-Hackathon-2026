from django.urls import path
from . import views

urlpatterns = [
    path("club/cod/", views.redeem_code, name="redeem_code"),
    path("realizari/", views.achievements, name="achievements"),
    path("clubul-meu/", views.club_corner, name="club_corner"),
]
