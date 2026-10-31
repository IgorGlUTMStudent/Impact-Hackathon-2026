"""Sign-up, login, dashboard, family, child report, PIN and child mode (contracts/routes.md rows 4–9, 16).

Templates: each view renders the UI owners' template (adult/…, child/…) when it exists and falls back to the
unstyled placeholder in apps/accounts/templates/accounts/. Context keys are listed per view.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.club.services import is_member
from apps.core.viewmodels import BookVM, ChildVM, GrantVM, ShelfEntryVM, percent
from apps.library.models import ShelfEntry
from apps.library.stats import reader_stats

from . import throttle
from .authz import (
    ACTIVE_CHILD_KEY, MODE_KEY, current_reader, get_child_for_guardian, is_child_mode, login_required,
)
from .forms import ChildForm, LoginForm, PinGateForm, PinSetForm, RenameChildForm, SignupForm
from .models import MAX_CHILDREN_PER_GUARDIAN, Account, Reader, Throttle, normalize_email

CHILD_HOME_URL = "/copil/"  # child_home lives in apps/core/urls.py (PR-8); path fixed by routes.md


def _templates(name, ui="adult"):
    return [f"{ui}/{name}.html", f"accounts/{name}.html"]


def _locked(request, template, context, locked):
    response = render(request, template, {**context, "locked_minutes": locked.minutes}, status=429)
    response["Retry-After"] = str(locked.retry_after)
    return response


class ThrottledLoginView(LoginView):
    """Context: form, next, locked_minutes (only on 429)."""

    template_name = _templates("login")
    authentication_form = LoginForm

    def get_template_names(self):
        return self.template_name  # already a list; the base class would wrap it in another one

    def post(self, request, *args, **kwargs):
        email = normalize_email(request.POST.get("username"))
        try:
            throttle.check(Throttle.LOGIN, email)
        except throttle.Locked as locked:
            return _locked(request, self.template_name, self.get_context_data(form=self.get_form()), locked)
        form = self.get_form()
        if form.is_valid():
            throttle.reset(Throttle.LOGIN, email)
            return self.form_valid(form)
        throttle.record_failure(Throttle.LOGIN, email)
        response = self.form_invalid(form)
        response.status_code = 422
        return response


@require_http_methods(["GET", "POST"])
def signup(request):
    """Context: form."""
    form = SignupForm(request.POST or None)
    if request.method == "POST":
        if not form.is_valid():
            return render(request, _templates("signup"), {"form": form}, status=422)
        with transaction.atomic():
            account = Account.objects.create_user(
                form.cleaned_data["email"], form.cleaned_data["password"], display_name=form.cleaned_data["display_name"]
            )
            Reader.objects.create(kind=Reader.ADULT, account=account)
        login(request, account, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, _templates("signup"), {"form": form})


def _child_vm(c):
    return ChildVM(c.public_id, c.nickname, c.avatar, c.age_band)


def _entry_vm(entry):
    book = entry.book
    return ShelfEntryVM(
        public_id=entry.public_id, book=BookVM(**{name: getattr(book, name) for name in BookVM.__dataclass_fields__}),
        current_page=entry.current_page, page_count=book.page_count,
        percent=percent(entry.current_page, book.page_count), status=entry.status,
    )


@never_cache
@login_required
@require_GET
def adult_dashboard(request):
    """Context: me {display_name}, my_stats StatsVM, children [{child ChildVM, stats StatsVM, current_entry
    ShelfEntryVM | None}]. Child mode never gets here: ChildModeMiddleware does not allow-list this route."""
    children = request.user.children.select_related("reader").order_by("created_at", "pk")
    # One query for all children: the newest unfinished book per reader wins, pk breaks added_at ties.
    current = {}
    for entry in ShelfEntry.objects.filter(
        reader__child__guardian=request.user, status=ShelfEntry.READING
    ).select_related("book").order_by("-added_at", "-pk"):
        current.setdefault(entry.reader_id, entry)
    return render(request, _templates("dashboard"), {
        "me": {"display_name": request.user.display_name},
        "my_stats": reader_stats(current_reader(request)),
        "children": [
            {
                "child": _child_vm(c),
                "stats": reader_stats(c.reader),
                "current_entry": _entry_vm(current[c.reader.pk]) if c.reader.pk in current else None,
            }
            for c in children
        ],
    })


@never_cache
@login_required
@require_GET
def child_report(request, child):
    """Read-only. Context: child ChildVM, stats StatsVM, entries [ShelfEntryVM], grants [GrantVM],
    memberships [{valid_until, status}] (history; a status of "active" may already be expired),
    is_member bool (current entitlement, the only field to trust for "member now")."""
    profile = get_child_for_guardian(request, child)  # foreign and unknown are the same 404
    reader = profile.reader
    entries = reader.shelf.select_related("book").order_by("-added_at", "-pk")
    grants = reader.grants.select_related("achievement").order_by("-granted_at", "-pk")
    return render(request, _templates("child_report"), {
        "child": _child_vm(profile),
        "stats": reader_stats(reader),
        "entries": [_entry_vm(e) for e in entries],
        "grants": [
            GrantVM(g.achievement.code, g.achievement.title, g.achievement.icon, g.granted_at, g.achievement.members_only)
            for g in grants
        ],
        "memberships": list(reader.memberships.order_by("-valid_until", "-pk").values("valid_until", "status")),
        "is_member": is_member(reader),
    })


def _family_context(request, **extra):
    children = request.user.children.order_by("created_at")
    return {
        "children": [ChildVM(c.public_id, c.nickname, c.avatar, c.age_band) for c in children],
        "form": ChildForm(),
        "pin_set": bool(request.user.pin_hash),
        "can_add_child": len(children) < MAX_CHILDREN_PER_GUARDIAN,
        **extra,
    }


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def family(request):
    """Context: children [ChildVM], form (create child), pin_set, can_add_child; on 422 also rename_form/rename_child."""
    if request.method == "GET":
        return render(request, _templates("family"), _family_context(request))
    form = ChildForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            # Lock the guardian row so two parallel submits cannot both pass the limit check.
            guardian = Account.objects.select_for_update().get(pk=request.user.pk)
            if guardian.children.count() >= MAX_CHILDREN_PER_GUARDIAN:
                form.add_error(None, f"Poți adăuga cel mult {MAX_CHILDREN_PER_GUARDIAN} copii.")
            else:
                child = form.save(commit=False)
                child.guardian = guardian
                child.save()
                Reader.objects.create(kind=Reader.CHILD, child=child)
                return redirect("family")
    return render(request, _templates("family"), _family_context(request, form=form), status=422)


@never_cache
@login_required
@require_POST
def child_rename(request, child):
    profile = get_child_for_guardian(request, child)
    form = RenameChildForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        return redirect("family")
    profile.refresh_from_db()  # the failed form already put the invalid nickname on the instance
    context = _family_context(request, rename_form=form, rename_child=ChildVM(
        profile.public_id, profile.nickname, profile.avatar, profile.age_band
    ))
    return render(request, _templates("family"), context, status=422)


@never_cache
@login_required
@require_POST
def child_delete(request, child):
    profile = get_child_for_guardian(request, child)
    if request.POST.get("confirm") != "1":  # deleting removes the child's whole reading history
        return render(request, _templates("family"), _family_context(request), status=422)
    profile.delete()
    return redirect("family")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def pin_set(request):
    """Context: form."""
    form = PinSetForm(request.user, request.POST or None)
    if request.method == "POST":
        if not form.is_valid():
            return render(request, _templates("pin_set"), {"form": form}, status=422)
        request.user.pin_hash = make_password(form.cleaned_data["pin"])
        request.user.save(update_fields=["pin_hash"])
        throttle.reset(Throttle.PIN, str(request.user.pk))  # the password re-auth proves the guardian
        return redirect("family")
    return render(request, _templates("pin_set"), {"form": form})


@login_required
@require_POST
def child_mode_start(request, child):
    profile = get_child_for_guardian(request, child)
    if not request.user.pin_hash:
        return redirect("pin_set")
    request.session[MODE_KEY] = "child"
    request.session[ACTIVE_CHILD_KEY] = str(profile.public_id)
    return redirect(CHILD_HOME_URL)


@login_required
@require_http_methods(["GET", "POST"])
def pin_gate(request):
    """Context: form, locked_minutes (only on 429). The recovery link POSTs to logout."""
    if not is_child_mode(request):
        return redirect(settings.LOGIN_REDIRECT_URL)
    template, key = _templates("pin_gate", ui="child"), str(request.user.pk)
    form = PinGateForm(request.POST or None)
    if request.method == "GET":
        return render(request, template, {"form": form})
    try:
        throttle.check(Throttle.PIN, key)
    except throttle.Locked as locked:
        return _locked(request, template, {"form": PinGateForm()}, locked)
    # Fail closed when the hash is missing (abnormal out-of-band state, #40): count the failure
    # instead of calling check_password with None, which would 500. Never unlocks adult mode.
    if form.is_valid() and request.user.pin_hash and check_password(form.cleaned_data["pin"], request.user.pin_hash):
        throttle.reset(Throttle.PIN, key)
        request.session.pop(MODE_KEY, None)
        request.session.pop(ACTIVE_CHILD_KEY, None)
        return redirect(settings.LOGIN_REDIRECT_URL)
    throttle.record_failure(Throttle.PIN, key)
    form.add_error(None, "PIN greșit.")
    return render(request, template, {"form": form}, status=422)
