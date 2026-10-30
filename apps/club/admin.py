from django.contrib import admin

from apps.accounts.admin import ReadOnlyAdmin

from .models import Achievement, AchievementGrant, ClubActivity, ClubMembership, MembershipCode

# Minimal registration. Activation/revocation and code issuing (plaintext shown once) are PR-5 admin actions.


@admin.register(ClubMembership)
class ClubMembershipAdmin(ReadOnlyAdmin):
    list_display = ["reader", "status", "valid_from", "valid_until", "source"]
    list_filter = ["status", "source"]
    fields = ["reader", "status", "valid_from", "valid_until", "source", "revoked_at"]


@admin.register(MembershipCode)
class MembershipCodeAdmin(ReadOnlyAdmin):
    list_display = ["label", "expires_at", "membership_days", "redeemed_at"]
    fields = ["label", "expires_at", "membership_days", "redeemed_at"]  # never the hash


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
