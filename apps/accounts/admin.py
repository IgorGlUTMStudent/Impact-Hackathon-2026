from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Account, ChildProfile, Reader, Throttle


@admin.register(Account)
class AccountAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_staff", "is_active"]
    search_fields = ["email", "display_name"]
    # pin_hash is deliberately absent: readonly fields still render their value, and a 4–6 digit PIN hash
    # is cheap to brute-force offline. The PIN is set and checked only by the app (PR-2).
    readonly_fields = ["last_login", "date_joined"]
    fieldsets = [
        (None, {"fields": ["email", "password", "display_name", "ui_language"]}),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "display_name", "password1", "password2"]}),
    ]


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Read-only also means no object delete or admin bulk delete, even for superusers.
        return False


@admin.register(ChildProfile)
class ChildProfileAdmin(ReadOnlyAdmin):
    # authorization.md: staff see children read-only, nickname only; guardians manage them in the app.
    list_display = ["nickname"]
    fields = ["nickname"]


@admin.register(Reader)
class ReaderAdmin(ReadOnlyAdmin):
    list_display = ["public_id", "kind"]
    fields = ["public_id", "kind"]


@admin.register(Throttle)
class ThrottleAdmin(ReadOnlyAdmin):
    list_display = ["scope", "failures", "window_started_at", "locked_until"]
    list_filter = ["scope"]
    fields = ["scope", "failures", "window_started_at", "locked_until"]
