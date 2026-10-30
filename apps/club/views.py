"""Club HTTP boundary. Session mode is enforced by the real child middleware."""
from django.contrib import messages
from django.db import OperationalError, connection
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters

from apps.accounts import authz, throttle
from apps.accounts.models import Reader
from apps.core.viewmodels import AchievementVM, ChildVM, GrantVM
from . import services
from .models import Achievement, AchievementGrant, ClubActivity


def _render(request, name, context, status=200):
    ui = "child" if authz.is_child_mode(request) else "adult"
    return render(request, [f"{ui}/{name}.html", f"club/{name}.html"], context, status=status)


def _is_db_lock(error):
    cause = error.__cause__
    sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    if sqlstate in {"55P03", "40P01"}:
        return True
    return connection.vendor == "sqlite" and (
        getattr(cause, "sqlite_errorcode", 0) & 255 in {5, 6}
        or str(error).lower() in {"database is locked", "database table is locked"}
    )


@never_cache
@authz.login_required
@sensitive_post_parameters("code")
@require_http_methods(["GET", "POST"])
def redeem_code(request):
    children = [ChildVM(c.public_id, c.nickname, c.avatar, c.age_band)
                for c in request.user.children.order_by("created_at", "pk")]
    context = {"children": children}
    if request.method == "GET":
        return _render(request, "redeem_code", context)
    try:
        target = request.POST.get("reader", "")
        if target == "self":
            reader = authz.current_reader(request)
        else:
            child = authz.get_child_for_guardian(request, target)
            try:
                reader = child.reader
            except Reader.DoesNotExist:
                raise Http404 from None
        membership = services.redeem_code(request.user, reader, request.POST.get("code", ""))
    except services.InvalidCode:
        return _render(request, "redeem_code", {**context, "error": "Cod invalid sau expirat"}, 422)
    except throttle.Locked as error:
        response = _render(request, "redeem_code", {
            **context, "error": "Prea multe încercări. Încearcă mai târziu.",
        }, 429)
        response["Retry-After"] = str(error.retry_after)
        return response
    except OperationalError as error:
        if not _is_db_lock(error):
            raise
        response = HttpResponse("Serviciu ocupat. Reîncearcă.", status=503)
        response["Retry-After"] = "5"
        return response
    messages.success(request, f"Membru al clubului până la {date_format(membership.valid_until, 'DATE_FORMAT')}.")
    if authz.is_htmx(request):
        return HttpResponse(status=200, headers={"HX-Redirect": reverse("redeem_code")})
    return redirect("redeem_code")


@never_cache
@authz.login_required
@require_GET
def achievements(request):
    reader = authz.current_reader(request)
    grants = list(AchievementGrant.objects.filter(reader=reader).select_related("achievement")
                  .order_by("achievement__code"))
    earned = [GrantVM(g.achievement.code, g.achievement.title, g.achievement.icon,
                      g.granted_at, g.achievement.members_only) for g in grants]
    earned_ids = {g.achievement_id for g in grants}
    locked = [{
        "achievement": AchievementVM(a.code, a.title, a.icon, a.members_only),
        "members_only": a.members_only,
        "hint": "Insigna asta e pentru membrii clubului." if a.members_only else a.description,
    } for a in Achievement.objects.exclude(pk__in=earned_ids).order_by("code")]
    return _render(request, "achievements", {"earned": earned, "locked": locked})


@never_cache
@authz.login_required
@require_GET
def club_corner(request):
    reader = authz.current_reader(request)
    if not services.is_member(reader):
        return HttpResponse("Acces rezervat membrilor clubului.", status=403)
    activities = list(ClubActivity.objects.filter(is_published=True).order_by("starts_at", "pk")
                      .values("title", "starts_at", "place"))
    return _render(request, "club_corner", {"activities": activities})
