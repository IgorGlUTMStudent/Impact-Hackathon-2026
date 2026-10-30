from django.contrib import admin
from django import forms
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone
import secrets

from apps.accounts.admin import ReadOnlyAdmin

from .models import Achievement, AchievementGrant, ClubActivity, ClubMembership, MembershipCode
from .services import code_digest, evaluate_achievements, revoke_membership
from django.db import transaction

# Minimal registration. Activation/revocation and code issuing (plaintext shown once) are PR-5 admin actions.


@admin.register(ClubMembership)
class ClubMembershipAdmin(admin.ModelAdmin):
    list_display = ["reader", "status", "valid_from", "valid_until", "source"]
    list_filter = ["status", "source"]
    fields = ["reader", "valid_from", "valid_until"]
    actions = ["revoke_selected"]

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        obj.source = ClubMembership.ADMIN
        obj.granted_by = request.user
        super().save_model(request, obj, form, change)
        evaluate_achievements(obj.reader)

    @admin.action(description="Revocă abonamentele selectate", permissions=["change"])
    def revoke_selected(self, request, queryset):
        for membership in queryset:
            revoke_membership(request.user, membership)


class CodeForm(forms.ModelForm):
    class Meta:
        model = MembershipCode
        fields = ["label", "expires_at", "membership_days"]

    def clean_expires_at(self):
        value = self.cleaned_data["expires_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Data trebuie să fie în viitor.")
        return value


@admin.register(MembershipCode)
class MembershipCodeAdmin(admin.ModelAdmin):
    form = CodeForm
    list_display = ["label", "expires_at", "membership_days", "redeemed_at"]
    fields = ["label", "expires_at", "membership_days"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        request._club_plaintext = secrets.token_hex(20).upper()
        obj.code_hash = code_digest(request._club_plaintext)
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        response = HttpResponse(format_html(
            "<h1>Cod creat</h1><p>Copiază acum; apare o singură dată.</p><code>{}</code>",
            request._club_plaintext,
        ))
        del request._club_plaintext
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "rule", "threshold", "members_only"]


@admin.register(AchievementGrant)
class AchievementGrantAdmin(ReadOnlyAdmin):
    list_display = ["achievement", "granted_at", "was_member"]
    fields = ["achievement", "granted_at", "was_member"]


@admin.register(ClubActivity)
class ClubActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "starts_at", "place", "is_published"]
    list_filter = ["is_published"]
