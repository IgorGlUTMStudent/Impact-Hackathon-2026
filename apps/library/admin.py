from django.contrib import admin

from apps.accounts.admin import ReadOnlyAdmin

from .models import Book, ProgressEvent, ShelfEntry


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "page_count", "age_band", "genre", "is_active"]
    list_filter = ["is_active", "genre", "age_band", "language"]
    search_fields = ["title", "author"]


@admin.register(ShelfEntry)
class ShelfEntryAdmin(ReadOnlyAdmin):
    # Progress is written only by library.services (PR-3); admin is for inspection.
    list_display = ["public_id", "book", "current_page", "status"]
    fields = ["public_id", "book", "current_page", "status", "added_at", "finished_at"]


@admin.register(ProgressEvent)
class ProgressEventAdmin(ReadOnlyAdmin):
    list_display = ["entry", "kind", "from_page", "to_page", "created_at"]
    fields = ["entry", "kind", "from_page", "to_page", "request_id", "created_at"]
