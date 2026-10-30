"""Sign-up, login, family, PIN and child mode (contracts/routes.md rows 4–9, 16).

Templates: each view renders the UI owners' template (adult/…, child/…) when it exists and falls back to the
unstyled placeholder in apps/accounts/templates/accounts/. Context keys are listed per view.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.viewmodels import ChildVM

from . import throttle
from .authz import ACTIVE_CHILD_KEY, MODE_KEY, get_child_for_guardian, is_child_mode, login_required
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


def _family_context(request, **extra):
    children = request.user.children.order_by("created_at")
    return {
        "children": [ChildVM(c.public_id, c.nickname, c.avatar, c.age_band) for c in children],
        "form": ChildForm(),
        "pin_set": bool(request.user.pin_hash),
        "can_add_child": len(children) < MAX_CHILDREN_PER_GUARDIAN,
        **extra,
    }


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


@login_required
@require_POST
def child_delete(request, child):
    profile = get_child_for_guardian(request, child)
    if request.POST.get("confirm") != "1":  # deleting removes the child's whole reading history
        return render(request, _templates("family"), _family_context(request), status=422)
    profile.delete()
    return redirect("family")


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
    if form.is_valid() and check_password(form.cleaned_data["pin"], request.user.pin_hash):
        throttle.reset(Throttle.PIN, key)
        request.session.pop(MODE_KEY, None)
        request.session.pop(ACTIVE_CHILD_KEY, None)
        return redirect(settings.LOGIN_REDIRECT_URL)
    throttle.record_failure(Throttle.PIN, key)
    form.add_error(None, "PIN greșit.")
    return render(request, template, {"form": form}, status=422)
