from django.urls import path

from apps.library import views

urlpatterns = [
    path("carti/", views.catalog, name="catalog"),
    path("carti/<uuid:book>/", views.book_detail, name="book_detail"),
    path("carti/<uuid:book>/adauga/", views.add_to_shelf, name="add_to_shelf"),
    path("raft/", views.my_shelf, name="my_shelf"),
    path("raft/<uuid:entry>/", views.shelf_entry, name="shelf_entry"),
    path("raft/<uuid:entry>/progres/", views.record_progress, name="record_progress"),
    path("raft/<uuid:entry>/terminat/", views.finish_book, name="finish_book"),
]
